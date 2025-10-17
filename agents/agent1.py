import os
import json
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from app.state import RecruitmentState
from tools.extraction_tools import get_extracted_cvs_for_job
from tools.shortlist_tools import save_shortlist

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("[Agent1 Error] GROQ_API_KEY not found")

def shortlist_node(state: RecruitmentState) -> RecruitmentState:
    """
    LangGraph node to shortlist candidates for a job using LLM.
    Updates the state with shortlisted candidates or an error.
    """
    print(f"[Agent1] Starting shortlist process for job_id={state['job_id']}")
    
    try:
        # Get job and CVs from state
        job = state["job"]
        if not job:
            state["status"] = "error"
            state["error"] = "Job details missing"
            print(f"[Agent1 Error] No job details for job_id={state['job_id']}")
            return state
        
        # Use tool to get CVs (already in state, but verify)
        if not state["cvs"]:
            job_id_to_title = {state["job_id"]: job.get("title", f"Job {state['job_id']}")}
            # Fixed: Direct function call instead of .invoke()
            state["cvs"] = get_extracted_cvs_for_job(
                job_id=state["job_id"],
                processed_dir=Path("data/processed"),
                job_id_to_title=job_id_to_title
            )
        
        if len(state["cvs"]) < 10:
            state["status"] = "error"
            state["error"] = f"Not enough CVs for shortlisting (only {len(state['cvs'])} CVs, need 10)"
            print(f"[Agent1 Error] {state['error']}")
            return state
        
        # Initialize LLM with error handling
        try:
            llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key=GROQ_API_KEY,
                temperature=0.0,
                max_tokens=1024,
                top_p=0.9
            )
        except Exception as e:
            state["status"] = "error"
            state["error"] = f"Failed to initialize LLM: {str(e)}"
            print(f"[Agent1 Error] {state['error']}")
            return state
        
        # Build prompt
        prompt = ChatPromptTemplate.from_template(
            """You are an expert recruiter. Here is a job description:
{job_description}

Here are the extracted CVs:
{cv_data}

Shortlist up to 5 CVs for this job based on the provided CV data. Only select CVs from the provided list; do not generate or include any fictional CVs. If fewer than 5 CVs meet the criteria, return only those that qualify. For each selected CV, provide a short justification.
Return ONLY a JSON list of dicts with keys: filename, name, email, phone, reason. Use the exact 'filename' provided for each CV (including .pdf extension). Do not include any explanation or extra text before or after the JSON."""
        )
        
        # Format CV data
        cv_data = ""
        for idx, cv in enumerate(state["cvs"], 1):
            cv_data += f"""
CV {idx}:
Filename: {cv['filename']}
Name: {cv['data'].get('name', 'N/A')}
Email: {cv['data'].get('email', 'N/A')}
Phone: {cv['data'].get('phone', 'N/A')}
Text: {cv['data'].get('raw_text', '')[:500]}
"""
        
        # Invoke LLM with error handling
        try:
            chain = prompt | llm
            response = chain.invoke({
                "job_description": job["description"], 
                "cv_data": cv_data
            })
            print(f"[Agent1] LLM Response: {response.content[:100]}...")
        except Exception as e:
            state["status"] = "error"
            state["error"] = f"LLM call failed: {str(e)}"
            print(f"[Agent1 Error] {state['error']}")
            return state
        
        # Parse response
        try:
            shortlisted = json.loads(response.content)
            
            # Ensure .pdf extension
            for entry in shortlisted:
                if not entry["filename"].endswith(".pdf"):
                    entry["filename"] += ".pdf"
                    
            state["shortlist"] = shortlisted
            state["status"] = "shortlisted"
            
            # Save shortlist using tool - Fixed: Direct function call
            save_shortlist(
                job_id=state["job_id"],
                shortlisted=shortlisted,
                processed_dir=Path("data/processed")
            )
            print(f"[Agent1] Successfully shortlisted {len(shortlisted)} candidates for job_id={state['job_id']}")
        
        except json.JSONDecodeError as e:
            state["status"] = "error"
            state["error"] = f"LLM returned invalid JSON: {str(e)}"
            print(f"[Agent1 Error] {state['error']}")
        
        except Exception as e:
            state["status"] = "error"
            state["error"] = f"Error saving shortlist: {str(e)}"
            print(f"[Agent1 Error] {state['error']}")
        
        return state
    
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"Unexpected error in shortlist_node: {str(e)}"
        print(f"[Agent1 Error] {state['error']}")
        return state