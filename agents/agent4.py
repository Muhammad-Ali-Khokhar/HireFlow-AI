import os
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, List, Any
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from app.state import RecruitmentState
from tools.calls_tools import get_call_data
from tools.final_tools import schedule_interview
from tools.screening_tools import get_shortlisted_cvs

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("[Agent4 Error] GROQ_API_KEY not found")

def extract_json_from_response(response_text: str) -> Dict:
    try:
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
            json_str = re.sub(r"(?<!\\)'([^']*)'(?=\s*[,}])", r'"\1"', json_str)
            json_str = re.sub(r"(?<!\\)'([^']*)'(?=\s*:)", r'"\1"', json_str)
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            return json.loads(json_str)
        return json.loads(response_text.strip())
    except Exception as e:
        print(f"[Agent4 Error] Failed to parse response: {e}")
        return {}

def load_cv_data(shortlist: List[Dict], job_id: str, processed_dir: str) -> Dict:
    cv_data = {}
    for entry in shortlist:
        filename = entry['filename']
        cv_file = Path(processed_dir) / f"{job_id}_{filename}.json"
        try:
            if cv_file.exists():
                with open(cv_file, "r", encoding="utf-8") as f:
                    cv_data[filename] = json.load(f)
                print(f"[Agent4] Loaded CV data for {filename}")
            else:
                cv_data[filename] = {}
                print(f"[Agent4] Warning: CV file not found for {filename}")
        except Exception as e:
            print(f"[Agent4 Error] Failed to load CV data for {filename}: {e}")
            cv_data[filename] = {}
    return cv_data

def save_final_picks_direct(job_id: str, final_picks: List[Dict], output_dir: str) -> bool:
    """Save final picks directly without using LangChain tool."""
    try:
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        final_file = output_dir_path / f"final_{job_id}.json"
        
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(final_picks, f, indent=2, ensure_ascii=False)
        print(f"[save_final_picks_direct] Saved final picks to {final_file}")
        return True
    except Exception as e:
        print(f"[save_final_picks_direct] Error saving final picks for job_id={job_id}: {e}")
        return False

def evaluate_candidate(llm, job: Dict, cv: Dict, transcript: str, filename: str) -> Dict:
    prompt = ChatPromptTemplate.from_template(
        """You are an HR expert. Evaluate the candidate's suitability for the role based on the job description, CV data, and call transcript. Provide a score (0-100) and a reason.
Job Description:
{job_description}
Candidate CV Data:
{cv_data}
Call Transcript:
{transcript}
Return a JSON object wrapped in ```json``` code blocks: ```json\n{{"filename": "{filename}", "score": int, "reason": "string"}}\n```"""
    )
    try:
        response = llm.invoke(prompt.format(
            job_description=job["description"],
            cv_data=json.dumps(cv, indent=2),
            transcript=transcript,
            filename=filename
        ))
        result = extract_json_from_response(response.content)
        if result and all(key in result for key in ['filename', 'score', 'reason']):
            result["name"] = cv.get("name", "Unknown Candidate")
            return result
        return {
            "filename": filename,
            "name": cv.get("name", "Unknown Candidate"),
            "score": 0,
            "reason": "Error: Invalid LLM response"
        }
    except Exception as e:
        print(f"[Agent4 Error] LLM failed for {filename}: {e}")
        return {
            "filename": filename,
            "name": cv.get("name", "Unknown Candidate"),
            "score": 0,
            "reason": f"Error: LLM failure - {str(e)}"
        }

def final_picks_node(state: RecruitmentState) -> RecruitmentState:
    """
    LangGraph node to select final candidates and schedule interviews.
    Updates the state with final picks or an error.
    """
    print(f"[Agent4] Starting final picks for job_id={state['job_id']}")
    
    try:
        # Validate inputs
        job = state["job"]
        if not job:
            state["status"] = "error"
            state["error"] = "Job details missing"
            print(f"[Agent4 Error] {state['error']}")
            return state
        
        # Get shortlisted candidates
        shortlist = state["shortlist"]
        if not shortlist:
            shortlist = get_shortlisted_cvs(
                job_id=state["job_id"],
                processed_dir=Path("data/processed"),
                shortlist_dir=Path("data/processed")
            )
            if not shortlist:
                state["status"] = "error"
                state["error"] = "No shortlisted candidates"
                print(f"[Agent4 Error] {state['error']}")
                return state
        
        # Get call data
        call_data = state["call_data"]
        if not call_data:
            call_data = get_call_data(state["job_id"], Path("data/processed"))
            if not call_data:
                state["status"] = "error"
                state["error"] = "No call data available"
                print(f"[Agent4 Error] {state['error']}")
                return state
        
        # Initialize LLM with error handling
        try:
            llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key=GROQ_API_KEY,
                temperature=0.2,
                max_tokens=8192
            )
        except Exception as e:
            state["status"] = "error"
            state["error"] = f"Failed to initialize LLM: {str(e)}"
            print(f"[Agent4 Error] {state['error']}")
            return state
        
        # Load CV data
        cv_data = load_cv_data(shortlist, state["job_id"], "data/processed")
        
        # Evaluate candidates
        final_picks = []
        for candidate in call_data:
            if candidate.get("call_status") != "done" or not candidate.get("transcript"):
                print(f"[Agent4] Skipping {candidate.get('filename', 'unknown')} - call not completed")
                continue
            filename = candidate["filename"]
            transcript = candidate["transcript"]
            cv = cv_data.get(filename, {})
            result = evaluate_candidate(llm, job, cv, transcript, filename)
            final_picks.append(result)
        
        if not final_picks:
            state["status"] = "error"
            state["error"] = "No valid candidates with completed calls found"
            print(f"[Agent4 Error] {state['error']}")
            return state
        
        # Sort and select top 3
        final_picks = sorted(final_picks, key=lambda x: x.get("score", 0), reverse=True)[:3]
        
        # Schedule interviews
        current_time = datetime.now(ZoneInfo("Asia/Karachi"))
        for i, pick in enumerate(final_picks):
            # Schedule 45 minutes apart starting from next hour
            interview_time = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1, minutes=i*45)
            pick["interview_time"] = interview_time.isoformat()
            
            # Get candidate details
            cv = cv_data.get(pick["filename"], {})
            candidate_name = cv.get("name", pick.get("name", "Unknown"))
            candidate_email = cv.get("email", "")
            
            # Schedule in Google Calendar and send emails
            scheduled_time = schedule_interview(
                job_id=state["job_id"],
                job_title=job.get("title", f"Job {state['job_id']}"),
                cv_filename=pick["filename"],
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                start_time=interview_time
            )
            
            if scheduled_time:
                pick["interview_time"] = scheduled_time.isoformat()
                print(f"[Agent4] Scheduled interview for {candidate_name} at {scheduled_time}")
            else:
                print(f"[Agent4] Failed to schedule interview for {candidate_name}")
        
        # Save final picks - FIXED: Use direct function call
        success = save_final_picks_direct(
            job_id=state["job_id"],
            final_picks=final_picks,
            output_dir="data/processed"
        )
        
        if not success:
            state["status"] = "error"
            state["error"] = "Failed to save final picks"
            print(f"[Agent4 Error] {state['error']}")
            return state
            
        state["final_picks"] = final_picks
        state["status"] = "final_picks_done"
        print(f"[Agent4] Generated {len(final_picks)} final picks for job_id={state['job_id']}")
        
        return state
    
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"Unexpected error in final_picks_node: {str(e)}"
        print(f"[Agent4 Error] {state['error']}")
        return state