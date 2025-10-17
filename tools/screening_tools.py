from pathlib import Path
import json
from .job_tools import get_job_details

def get_candidate_screening_questions(job_id: str, filename: str, processed_dir: Path):
    """Return screening questions for a single candidate (by filename) for a given job_id."""
    all_questions = get_screening_questions(job_id, processed_dir)
    for entry in all_questions:
        if entry.get("filename") == filename:
            return entry.get("questions", [])
    return []

def screening_questions_exist(job_id: str, processed_dir: Path):
    """Check if screening questions already exist and are valid for a job_id."""
    in_file = processed_dir / f"screening_{job_id}.json"
    if not in_file.exists():
        print(f"[screening_questions_exist] No screening file found: {in_file}")
        return False
    try:
        with open(in_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[screening_questions_exist] Found valid screening file with {len(data)} entries")
        return bool(data)  # Return True only if file has data
    except json.JSONDecodeError as e:
        print(f"[screening_questions_exist] Invalid JSON in {in_file}: {e}")
        return False

def format_hr_email(job_id: str, processed_dir: Path, jobs_file: Path):
    """Return a formatted email string for HR with candidate names, CV links, and screening questions."""
    questions = get_screening_questions(job_id, processed_dir)
    job = get_job_details(job_id, jobs_file)
    job_title = job.get('title', f"Job ID {job_id}")
    
    lines = []
    lines.append("Dear HR Team,")
    lines.append("")
    lines.append(f"Below are the screening questions and candidate details for the position '{job_title}'.")
    lines.append(f"These questions are tailored to evaluate candidates based on the job requirements and their submitted CVs.")
    lines.append("")
    lines.append("-" * 50)
    lines.append(f"Position: {job_title}")
    lines.append("-" * 50)
    lines.append("")
    
    for entry in questions:
        filename = entry['filename']
        cv_filename = filename if filename.endswith('.pdf') else f"{filename}.pdf"
        lines.append(f"Candidate: {filename}")
        lines.append(f"CV: http://localhost:8080/cvs/{job_id}_{cv_filename}")
        lines.append("")
        lines.append("Screening Questions:")
        for idx, q in enumerate(entry.get('questions', []), 1):
            lines.append(f"  {idx}. {q.get('question', 'No question available')}")
            if q.get('expected_answer'):
                lines.append(f"     Expected Response: {q.get('expected_answer')}")
            lines.append("")
        lines.append("-" * 50)
        lines.append("")
    
    lines.append("Please review the candidates and their respective screening questions. Let us know if you need further assistance or additional information.")
    lines.append("")
    lines.append("Best regards,")
    lines.append("HiringBot Team")
    lines.append("QuantumTech Recruitment System")
    
    return "\n".join(lines)

def get_shortlisted_cvs(job_id: str, processed_dir: Path, shortlist_dir: Path):
    """Return list of extracted CV data and reasons for shortlisted candidates for a given job_id."""
    shortlist_file = shortlist_dir / f"shortlist_{job_id}.json"
    if not shortlist_file.exists():
        return []
    with open(shortlist_file, "r", encoding="utf-8") as f:
        shortlist = json.load(f)
    cvs = []
    for entry in shortlist:
        cv_file = processed_dir / f"{job_id}_{entry['filename']}.json"
        if cv_file.exists():
            with open(cv_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            cvs.append({
                "filename": entry["filename"],
                "reason": entry.get("reason", ""),
                "data": data
            })
    return cvs

def save_screening_questions(job_id: str, questions: list, processed_dir: Path):
    out_file = processed_dir / f"screening_{job_id}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2)

def get_screening_questions(job_id: str, processed_dir: Path):
    in_file = processed_dir / f"screening_{job_id}.json"
    if not in_file.exists():
        return []
    with open(in_file, "r", encoding="utf-8") as f:
        return json.load(f)