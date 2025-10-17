from fastapi import FastAPI, Request, UploadFile, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pdfplumber
import re
from pathlib import Path
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo
import json
from app.workflow import app as graph_app
from app.state import RecruitmentState
from agents.agent3 import audio_processing_node
from tools.job_tools import get_job_details
from tools.extraction_tools import get_extracted_cvs_for_job
from tools.shortlist_tools import get_shortlist
from tools.calls_tools import get_call_data, save_call_data
from tools.final_tools import get_final_picks
from tools.screening_tools import get_screening_questions

app = FastAPI()

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
CV_DIR = DATA_DIR / "cvs"
JOBS_FILE = DATA_DIR / "jobs.json"

# Mount static and templates
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/cvs", StaticFiles(directory=CV_DIR), name="cvs")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Custom Jinja2 filter for formatting datetime
def format_datetime(iso_string: str) -> str:
    if not iso_string:
        return "Not scheduled"
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%A, %B %d, %Y, %I:%M %p PKT")
    except ValueError:
        return "Invalid date format"

templates.env.filters['format_datetime'] = format_datetime

# Load job listings
def load_jobs():
    try:
        with open(JOBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[load_jobs Error] Failed to load jobs: {e}")
        return []

def build_jobs_with_candidates():
    jobs = load_jobs()
    jobs_with_candidates = []

    for job in jobs:
        job_id = str(job['id'])
        shortlist = get_shortlist(job_id, DATA_DIR / "processed")
        call_data = get_call_data(job_id, DATA_DIR / "processed")

        candidates = []
        for entry in shortlist:
            candidate_data = {
                "filename": entry["filename"],
                "call_status": "not_done",
                "transcript": ""
            }
            for call_entry in call_data:
                if call_entry["filename"] == entry["filename"]:
                    candidate_data.update({
                        "call_status": call_entry.get("call_status", "not_done"),
                        "transcript": call_entry.get("transcript", "")
                    })
                    break
            candidates.append(candidate_data)

        jobs_with_candidates.append({
            'id': job_id,
            'title': job['title'],
            'candidates': candidates
        })

    return jobs_with_candidates

# Routes
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/jobs", response_class=HTMLResponse)
async def jobs(request: Request):
    jobs = load_jobs()
    if not jobs:
        print("[jobs] No jobs loaded")
        return templates.TemplateResponse("jobs.html", {
            "request": request,
            "jobs": [],
            "message": "No jobs available"
        })
    return templates.TemplateResponse("jobs.html", {"request": request, "jobs": jobs})

@app.post("/apply", response_class=HTMLResponse)
async def apply_job(request: Request, job_id: str = Form(...), cv: UploadFile = Form(...)):
    jobs = load_jobs()
    valid_job_ids = {str(job['id']) for job in jobs}
    if job_id not in valid_job_ids:
        print(f"[apply_job] Invalid job_id: {job_id}")
        return templates.TemplateResponse("jobs.html", {
            "request": request,
            "jobs": jobs,
            "message": f"Error: Invalid Job ID {job_id}"
        })

    # Save CV
    cv_filename = cv.filename if cv.filename.endswith('.pdf') else f"{cv.filename}.pdf"
    cv_path = CV_DIR / f"{job_id}_{cv_filename}"
    try:
        with open(cv_path, "wb") as buffer:
            shutil.copyfileobj(cv.file, buffer)
    except Exception as e:
        print(f"[apply_job] Error saving CV {cv_filename}: {e}")
        return templates.TemplateResponse("jobs.html", {
            "request": request,
            "jobs": jobs,
            "message": f"Error saving CV: {str(e)}"
        })

    # Extract data immediately
    processed_path = None
    if cv_filename.lower().endswith('.pdf'):
        try:
            with pdfplumber.open(cv_path) as pdf:
                text = "\n".join(page.extract_text() or '' for page in pdf.pages)
            name = text.split('\n')[0].strip()
            email = re.search(r"[\w\.-]+@[\w\.-]+", text)
            phone = re.search(r"(\+?\d[\d\s\-]{7,}\d)", text)
            extracted = {
                "name": name,
                "email": email.group(0) if email else '',
                "phone": phone.group(0) if phone else '',
                "raw_text": text[:2000]
            }
            processed_path = DATA_DIR / "processed" / f"{job_id}_{cv_filename}.json"
            with open(processed_path, "w", encoding="utf-8") as f:
                json.dump(extracted, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[apply_job] Extraction failed for {cv_filename}: {e}")

    # Trigger workflow only if CV count >=10 and no shortlist exists
    job_id_to_title = {str(job['id']): job['title'] for job in jobs}
    cvs = get_extracted_cvs_for_job(job_id, DATA_DIR / "processed", job_id_to_title)
    shortlist = get_shortlist(job_id, DATA_DIR / "processed")
    if len(cvs) >= 10 and not shortlist:
        try:
            state = RecruitmentState(
                job_id=job_id,
                job=None,
                cvs=[],
                shortlist=[],
                screening_questions=[],
                call_data=[],
                final_picks=[],
                status="init",
                error=None
            )
            result = await graph_app.ainvoke(state)
            print(f"[apply_job] Workflow result for job_id={job_id}: {result['status']}")
            if result["error"]:
                print(f"[apply_job] Workflow error: {result['error']}")
        except Exception as e:
            print(f"[apply_job] Workflow failed for job_id={job_id}: {e}")

    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "jobs": jobs,
        "message": f"Successfully uploaded CV for Job ID {job_id}"
    })

@app.get("/applications", response_class=HTMLResponse)
async def applications(request: Request):
    jobs = load_jobs()
    job_id_to_title = {str(job['id']): job['title'] for job in jobs}
    applications_by_job = {}
    try:
        for f in CV_DIR.iterdir():
            if not f.is_file():
                continue
            parts = f.name.split('_', 1)
            if len(parts) != 2:
                continue
            job_id, filename = parts
            job_title = job_id_to_title.get(job_id, f"Job {job_id}")
            filetype = 'pdf' if filename.lower().endswith('.pdf') else 'other'
            url = f"/cvs/{f.name}"
            preview_url = f"/preview/{f.name}"
            cv_info = {"filename": filename, "filetype": filetype, "url": url, "preview_url": preview_url}
            if job_title not in applications_by_job:
                applications_by_job[job_title] = []
            applications_by_job[job_title].append(cv_info)
    except Exception as e:
        print(f"[applications] Error processing CV directory: {e}")
        return templates.TemplateResponse("applications.html", {
            "request": request,
            "applications_by_job": {},
            "message": "Error loading applications"
        })
    
    return templates.TemplateResponse("applications.html", {
        "request": request,
        "applications_by_job": applications_by_job
    })

@app.get("/preview/{filename}", response_class=HTMLResponse)
async def preview_pdf(request: Request, filename: str):
    file_path = CV_DIR / filename
    if not file_path.exists() or not filename.lower().endswith('.pdf'):
        print(f"[preview_pdf] File not found or not a PDF: {filename}")
        return HTMLResponse("<h2>File not found or not a PDF.</h2>", status_code=404)
    return templates.TemplateResponse("pdf_preview.html", {
        "request": request,
        "pdf_url": f"/cvs/{filename}",
        "filename": filename
    })

@app.get("/extraction", response_class=HTMLResponse)
async def extraction(request: Request):
    jobs = load_jobs()
    job_id_to_title = {str(job['id']): job['title'] for job in jobs}
    processed_dir = DATA_DIR / "processed"
    extracted_by_job = {}
    
    for job_id, job_title in job_id_to_title.items():
        cvs = get_extracted_cvs_for_job(job_id, processed_dir, job_id_to_title)
        if cvs:
            extracted_by_job[job_title] = cvs
    
    print(f"[extraction] Loaded {len(extracted_by_job)} jobs with extracted CVs")
    if not extracted_by_job:
        return templates.TemplateResponse("extraction.html", {
            "request": request,
            "extracted_by_job": {},
            "message": "No extracted CVs found"
        })
    
    return templates.TemplateResponse("extraction.html", {
        "request": request,
        "extracted_by_job": extracted_by_job
    })

@app.get("/shortlist", response_class=HTMLResponse)
async def shortlist_select(request: Request):
    jobs = load_jobs()
    if not jobs:
        return templates.TemplateResponse("shortlist_select.html", {
            "request": request,
            "jobs": [],
            "message": "No jobs available"
        })
    return templates.TemplateResponse("shortlist_select.html", {"request": request, "jobs": jobs})

@app.get("/shortlist/{job_id}", response_class=HTMLResponse)
async def show_shortlist(request: Request, job_id: str, force_regenerate: bool = False):
    jobs = load_jobs()
    job_id_to_title = {str(job['id']): job['title'] for job in jobs}
    if job_id not in job_id_to_title:
        return templates.TemplateResponse("shortlist_select.html", {
            "request": request,
            "jobs": jobs,
            "message": f"Invalid Job ID {job_id}"
        })
    
    shortlist = get_shortlist(job_id, DATA_DIR / "processed")
    cv_count = len(get_extracted_cvs_for_job(job_id, DATA_DIR / "processed", job_id_to_title))
    error_message = None
    
    if force_regenerate or not shortlist:
        try:
            state = RecruitmentState(
                job_id=job_id,
                job=get_job_details(job_id, JOBS_FILE),
                cvs=[],
                shortlist=[],
                screening_questions=[],
                call_data=[],
                final_picks=[],
                status="init",
                error=None
            )
            result = await graph_app.ainvoke(state)
            shortlist = result["shortlist"]
            error_message = result["error"]
            print(f"[show_shortlist] Workflow result for job_id={job_id}: {result['status']}")
        except Exception as e:
            error_message = f"Workflow failed: {str(e)}"
            print(f"[show_shortlist] Workflow failed for job_id={job_id}: {e}")
    
    return templates.TemplateResponse("shortlist.html", {
        "request": request,
        "shortlisted": shortlist,
        "job_title": job_id_to_title.get(job_id, f"Job {job_id}"),
        "cv_count": cv_count,
        "error_message": error_message
    })

@app.get("/screening", response_class=HTMLResponse)
async def screening_select(request: Request):
    jobs = load_jobs()
    if not jobs:
        return templates.TemplateResponse("screening.html", {
            "request": request,
            "jobs": [],
            "message": "No jobs available"
        })
    return templates.TemplateResponse("screening.html", {"request": request, "jobs": jobs})

@app.get("/screening/{job_id}", response_class=HTMLResponse)
async def show_screening_questions(request: Request, job_id: str):
    jobs = load_jobs()
    job_id_to_title = {str(job['id']): job['title'] for job in jobs}
    if job_id not in job_id_to_title:
        return templates.TemplateResponse("screening.html", {
            "request": request,
            "jobs": jobs,
            "message": f"Invalid Job ID {job_id}"
        })
    
    screening_data = get_screening_questions(job_id, DATA_DIR / "processed")
    print(f"[show_screening_questions] Loaded {len(screening_data)} screening entries for job_id={job_id}")
    return templates.TemplateResponse("screening.html", {
        "request": request,
        "screening_data": screening_data,
        "job_title": job_id_to_title.get(job_id, f"Job {job_id}"),
        "job_id": job_id,
        "jobs": jobs
    })

@app.get("/calls", response_class=HTMLResponse)
async def calls_management(request: Request):
    jobs_with_candidates = build_jobs_with_candidates()
    return templates.TemplateResponse("calls.html", {
        "request": request,
        "jobs_with_candidates": jobs_with_candidates
    })

@app.post("/calls/{job_id}/upload_transcript", response_class=HTMLResponse)
async def upload_transcript(request: Request, job_id: str, filename: str = Form(...), transcript: UploadFile = Form(...)):
    jobs = load_jobs()
    job_id_to_title = {str(job['id']): job['title'] for job in jobs}
    if job_id not in job_id_to_title:
        return templates.TemplateResponse("calls.html", {
            "request": request,
            "jobs_with_candidates": [],
            "message": f"Error: Invalid Job ID {job_id}"
        })

    processed_dir = DATA_DIR / "processed"
    shortlist = get_shortlist(job_id, processed_dir)
    if not any(entry["filename"] == filename for entry in shortlist):
        return templates.TemplateResponse("calls.html", {
            "request": request,
            "jobs_with_candidates": [],
            "message": f"Error: Candidate {filename} not in shortlist"
        })

    try:
        # Validate file type
        file_extension = Path(transcript.filename).suffix.lower()
        if file_extension not in ['.txt', '.mp3', '.wav']:
            return templates.TemplateResponse("calls.html", {
                "request": request,
                "jobs_with_candidates": [],
                "message": "Error: File must be .txt, .mp3, or .wav format"
            })

        # Save uploaded file temporarily
        temp_filename = f"{job_id}_{filename}_{transcript.filename}"
        temp_path = DATA_DIR / "temp" / temp_filename
        temp_path.parent.mkdir(exist_ok=True)
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(transcript.file, buffer)

        # Process file using Agent 3
        if file_extension == '.txt':
            # Handle text file directly (existing logic)
            with open(temp_path, "r", encoding="utf-8") as f:
                transcript_text = f.read()
        else:
            # Use Agent 3 for audio processing
            state = RecruitmentState(
                job_id=job_id,
                job=None,
                cvs=[],
                shortlist=[],
                screening_questions=[],
                call_data=[],
                final_picks=[],
                status="init",
                error=None,
                audio_file_path=str(temp_path),
                candidate_filename=filename
            )
            
            result = audio_processing_node(state)
            
            if result["status"] == "error":
                # Clean up temp file
                if temp_path.exists():
                    temp_path.unlink()
                return templates.TemplateResponse("calls.html", {
                    "request": request,
                    "jobs_with_candidates": [],
                    "message": f"Error processing audio: {result['error']}"
                })
            
            transcript_text = result["processed_transcript"]

        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()

        # Update call data (existing logic)
        call_data = get_call_data(job_id, processed_dir)
        updated = False
        for entry in call_data:
            if entry["filename"] == filename:
                entry["call_status"] = "done"
                entry["transcript"] = transcript_text
                updated = True
                break
        if not updated:
            call_data.append({
                "filename": filename,
                "call_status": "done",
                "transcript": transcript_text
            })

        save_call_data(job_id, call_data, processed_dir)

        # Trigger workflow if all transcripts complete (existing logic)
        shortlist_filenames = {entry["filename"] for entry in shortlist}
        call_filenames = {entry["filename"] for entry in call_data if entry.get("call_status") == "done" and entry.get("transcript")}
        if shortlist_filenames.issubset(call_filenames):
            try:
                state = RecruitmentState(
                    job_id=job_id,
                    job=get_job_details(job_id, JOBS_FILE),
                    cvs=[],
                    shortlist=[],
                    screening_questions=[],
                    call_data=[],
                    final_picks=[],
                    status="init",
                    error=None
                )
                result = await graph_app.ainvoke(state)
                print(f"[upload_transcript] Workflow result for job_id={job_id}: {result['status']}")
                if result["error"]:
                    print(f"[upload_transcript] Workflow error: {result['error']}")
            except Exception as e:
                print(f"[upload_transcript] Workflow failed for job_id={job_id}: {e}")

        # Return success response (existing logic)
        candidates = []
        for entry in shortlist:
            candidate_data = {
                "filename": entry["filename"],
                "call_status": "not_done",
                "transcript": ""
            }
            for call_entry in call_data:
                if call_entry["filename"] == entry["filename"]:
                    candidate_data.update({
                        "call_status": call_entry.get("call_status", "not_done"),
                        "transcript": call_entry.get("transcript", "")
                    })
                    break
            candidates.append(candidate_data)

        jobs_with_candidates = build_jobs_with_candidates()

        return templates.TemplateResponse("calls.html", {
            "request": request,
            "jobs_with_candidates": jobs_with_candidates,
            "message": f"Transcript processed successfully for {filename}"
        })

    except Exception as e:
        # Clean up temp file on error
        if 'temp_path' in locals() and temp_path.exists():
            temp_path.unlink()
        print(f"[upload_transcript] Error processing transcript for {filename}: {e}")
        return templates.TemplateResponse("calls.html", {
            "request": request,
            "jobs_with_candidates": [],
            "message": f"Error processing transcript: {str(e)}"
        })

@app.get("/final", response_class=HTMLResponse)
async def final_picks(request: Request):
    jobs = load_jobs()
    all_jobs = []
    
    for job in jobs:
        job_id = str(job['id'])
        final_picks = get_final_picks(job_id, DATA_DIR / "processed")
        all_jobs.append({
            'id': job_id,
            'title': job['title'],
            'final_picks': final_picks
        })
    
    return templates.TemplateResponse("final.html", {
        "request": request,
        "all_jobs": all_jobs
    })