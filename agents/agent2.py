import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
from typing import Dict, List, Any
import base64
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from app.state import RecruitmentState
from tools.screening_tools import get_shortlisted_cvs, format_hr_email
from tools.shortlist_tools import get_shortlist

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "quantumtech.4321@gmail.com")
HR_EMAIL = os.getenv("HR_EMAIL", "mali.sm.khokhar@gmail.com")

if not GROQ_API_KEY:
    print("[Agent2 Error] GROQ_API_KEY not found")

def create_message(sender: str, to: str, subject: str, message_text: str) -> Dict:
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': raw}

def send_email(service, sender: str, to: str, subject: str, message_text: str) -> bool:
    try:
        message = create_message(sender, to, subject, message_text)
        sent_message = service.users().messages().send(userId=sender, body=message).execute()
        print(f"[Agent2] Email sent to {to} with ID: {sent_message['id']}")
        return True
    except HttpError as error:
        print(f"[Agent2 Error] Failed to send email: {error}")
        return False

def get_gmail_service():
    try:
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', ['https://www.googleapis.com/auth/gmail.send'])
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                print("[Agent2 Error] Run auth_gmail.py to generate token.json")
                return None
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        print(f"[Agent2 Error] Failed to initialize Gmail service: {e}")
        return None

def extract_json_from_response(response_text: str) -> List:
    try:
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```|(\[.*?\])', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1) or json_match.group(2)
            return json.loads(json_str.strip())
        print("[Agent2] No JSON found in response")
        return []
    except Exception as e:
        print(f"[Agent2 Error] Failed to parse response: {e}")
        return []

def save_screening_questions(job_id: str, questions: List[Dict], output_dir: str) -> bool:
    """Save the screening questions to a JSON file."""
    try:
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        output_file = output_dir_path / f"screening_{job_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        print(f"[save_screening_questions] Saved screening questions for job_id={job_id} to {output_file}")
        return True
    except Exception as e:
        print(f"[save_screening_questions] Error saving questions for job_id={job_id}: {e}")
        return False

def screening_node(state: RecruitmentState) -> RecruitmentState:
    """
    LangGraph node to generate screening questions for shortlisted candidates and send HR notification.
    Updates the state with screening questions or an error.
    """
    print(f"[Agent2] Starting screening questions for job_id={state['job_id']}")
    
    try:
        # Get job and shortlist from state
        job = state["job"]
        if not job:
            state["status"] = "error"
            state["error"] = "Job details missing"
            print(f"[Agent2 Error] No job details for job_id={state['job_id']}")
            return state
        
        # Get shortlisted CVs - Fixed: Use correct function
        if not state["shortlist"]:
            # Try to load from file if not in state
            shortlist = get_shortlist(state["job_id"], Path("data/processed"))
            if not shortlist:
                state["status"] = "error"
                state["error"] = "No shortlisted candidates"
                print(f"[Agent2 Error] {state['error']}")
                return state
            state["shortlist"] = shortlist
        
        shortlisted_cvs = get_shortlisted_cvs(
            job_id=state["job_id"],
            processed_dir=Path("data/processed"),
            shortlist_dir=Path("data/processed")
        )
        
        if not shortlisted_cvs:
            state["status"] = "error"
            state["error"] = "Failed to load shortlisted CVs"
            print(f"[Agent2 Error] {state['error']}")
            return state
        
        # Initialize LLM with error handling
        try:
            llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key=GROQ_API_KEY,
                temperature=0.2,
                max_tokens=2048
            )
        except Exception as e:
            state["status"] = "error"
            state["error"] = f"Failed to initialize LLM: {str(e)}"
            print(f"[Agent2 Error] {state['error']}")
            return state
        
        prompt = ChatPromptTemplate.from_template(
            """You are an HR assistant. Given the job description, candidate CV data, and shortlisting reason, generate 5 or more tailored screening call questions for this candidate. Questions should be technical and based on the candidate's experience and skills.
Job Description:
{job_description}
Candidate Extracted Data:
{cv_data}
Shortlisting Reason: {reason}
Return a JSON list of objects with 'question' and 'expected_answer' fields, e.g., [{{"question": "Example", "expected_answer": "Details"}}]. Return ONLY the JSON list."""
        )
        
        questions_out = []
        for cv in shortlisted_cvs:
            filename = cv['filename']
            print(f"[Agent2] Processing CV: {filename}")
            
            try:
                response = llm.invoke(prompt.format(
                    job_description=job["description"],
                    cv_data=json.dumps(cv["data"], indent=2),
                    reason=cv["reason"]
                ))
                questions = extract_json_from_response(response.content)
                if not questions:
                    questions = [{"question": "Error: Invalid response format", "expected_answer": ""}]
                questions_out.append({"filename": filename, "questions": questions})
            except Exception as e:
                print(f"[Agent2 Error] LLM failed for {filename}: {e}")
                questions_out.append({"filename": filename, "questions": [{"question": f"Error: {str(e)}", "expected_answer": ""}]})
        
        # Save questions - Fixed: Direct function call
        success = save_screening_questions(
            job_id=state["job_id"],
            questions=questions_out,
            output_dir="data/processed"
        )
        
        if not success:
            state["status"] = "error"
            state["error"] = "Failed to save screening questions"
            print(f"[Agent2 Error] {state['error']}")
            return state
            
        state["screening_questions"] = questions_out
        state["status"] = "screening_done"
        
        # Send email to HR
        try:
            email_content = format_hr_email(state["job_id"], Path("data/processed"), Path("data/jobs.json"))
            service = get_gmail_service()
            if service:
                send_email(
                    service, SENDER_EMAIL, HR_EMAIL,
                    f"Screening Questions and CVs for Job ID {state['job_id']}",
                    email_content
                )
            else:
                print("[Agent2] Warning: Gmail service unavailable, email not sent")
        except Exception as e:
            print(f"[Agent2] Warning: Email sending failed: {e}")
            # Don't fail the whole process for email issues
        
        print(f"[Agent2] Generated {len(questions_out)} question sets for job_id={state['job_id']}")
        return state
    
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"Unexpected error in screening_node: {str(e)}"
        print(f"[Agent2 Error] {state['error']}")
        return state