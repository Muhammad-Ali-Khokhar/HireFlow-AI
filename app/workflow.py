from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from pathlib import Path
import sys
# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from app.state import RecruitmentState
from agents.agent1 import shortlist_node
from agents.agent2 import screening_node
from agents.agent4 import final_picks_node
from tools.extraction_tools import get_extracted_cvs_for_job
from tools.calls_tools import get_call_data
from tools.job_tools import get_job_details
from tools.shortlist_tools import get_shortlist
from tools.screening_tools import get_screening_questions
from tools.final_tools import get_final_picks

# Get base directory for relative paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
JOBS_FILE = DATA_DIR / "jobs.json"

# Conditional edge functions - FIXED: Don't modify state here
def check_cv_count(state: RecruitmentState) -> str:
    """Check if enough CVs (10 or more) are available and shortlist doesn't exist."""
    existing_shortlist = get_shortlist(state["job_id"], PROCESSED_DIR)
    if existing_shortlist:
        print(f"[workflow] Existing shortlist found for job_id={state['job_id']}, skipping to screening check")
        return "load_existing_shortlist"
    if len(state["cvs"]) >= 10:
        print(f"[workflow] Sufficient CVs ({len(state['cvs'])}) for job_id={state['job_id']}, proceeding to shortlist")
        return "shortlist"
    print(f"[workflow] Waiting for more CVs for job_id={state['job_id']}: only {len(state['cvs'])}, need 10")
    return "wait"

def check_screening_exists(state: RecruitmentState) -> str:
    """Check if screening questions already exist."""
    existing_questions = get_screening_questions(state["job_id"], PROCESSED_DIR)
    if existing_questions:
        print(f"[workflow] Existing screening questions found for job_id={state['job_id']}, skipping to calls")
        return "load_existing_screening"
    if not state["shortlist"]:
        print(f"[workflow] No shortlist for job_id={state['job_id']}")
        return "wait"
    return "screening"

def check_calls_done(state: RecruitmentState) -> str:
    """Check if all calls are done and final picks don't exist."""
    existing_final = get_final_picks(state["job_id"], PROCESSED_DIR)
    if existing_final:
        print(f"[workflow] Existing final picks found for job_id={state['job_id']}, workflow complete")
        return "load_existing_final"
    
    call_data = state["call_data"]
    shortlist = state["shortlist"]
    
    if not shortlist:
        print(f"[workflow] No shortlist for job_id={state['job_id']}")
        return "wait"
    if not call_data:
        print(f"[workflow] No call data for job_id={state['job_id']}")
        return "wait"
    
    shortlist_filenames = {entry["filename"] for entry in shortlist}
    call_filenames = {
        entry["filename"]
        for entry in call_data
        if entry.get("call_status") == "done" and entry.get("transcript")
    }
    
    if shortlist_filenames.issubset(call_filenames):
        print(f"[workflow] All calls completed for job_id={state['job_id']}, proceeding to final picks")
        return "final_picks"
    
    print(f"[workflow] Waiting for call completion for job_id={state['job_id']}")
    return "wait"

# Node to load job details
def load_job_node(state: RecruitmentState) -> RecruitmentState:
    """Load job details from jobs.json."""
    try:
        job = get_job_details(state["job_id"], JOBS_FILE)
        if not job:
            state["status"] = "error"
            state["error"] = f"Job not found for job_id={state['job_id']}"
            print(f"[workflow] Job not found for job_id={state['job_id']}")
        else:
            state["job"] = job
            state["status"] = "job_loaded"
            print(f"[workflow] Loaded job: {job.get('title', 'Unknown')} for job_id={state['job_id']}")
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"Error loading job: {str(e)}"
        print(f"[workflow] Error loading job for job_id={state['job_id']}: {e}")
    return state

# Node to extract CVs
def extract_cvs_node(state: RecruitmentState) -> RecruitmentState:
    """Extract CVs for the given job_id."""
    try:
        job_id_to_title = {state["job_id"]: state["job"].get("title", f"Job {state['job_id']}")} if state["job"] else {}
        state["cvs"] = get_extracted_cvs_for_job(
            job_id=state["job_id"],
            processed_dir=PROCESSED_DIR,
            job_id_to_title=job_id_to_title
        )
        state["status"] = "cvs_extracted"
        print(f"[workflow] Extracted {len(state['cvs'])} CVs for job_id={state['job_id']}")
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"Error extracting CVs: {str(e)}"
        print(f"[workflow] Error extracting CVs for job_id={state['job_id']}: {e}")
    return state

# Node to load existing shortlist
def load_existing_shortlist_node(state: RecruitmentState) -> RecruitmentState:
    """Load existing shortlist if available."""
    try:
        existing_shortlist = get_shortlist(state["job_id"], PROCESSED_DIR)
        if existing_shortlist:
            state["shortlist"] = existing_shortlist
            state["status"] = "shortlist_loaded"
            print(f"[workflow] Loaded existing shortlist with {len(existing_shortlist)} candidates for job_id={state['job_id']}")
        else:
            state["status"] = "error"
            state["error"] = "Expected shortlist not found"
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"Error loading existing shortlist: {str(e)}"
        print(f"[workflow] Error loading shortlist for job_id={state['job_id']}: {e}")
    return state

# Node to load existing screening questions
def load_existing_screening_node(state: RecruitmentState) -> RecruitmentState:
    """Load existing screening questions if available."""
    try:
        existing_questions = get_screening_questions(state["job_id"], PROCESSED_DIR)
        if existing_questions:
            state["screening_questions"] = existing_questions
            state["status"] = "screening_loaded"
            print(f"[workflow] Loaded existing screening questions for job_id={state['job_id']}")
        else:
            state["status"] = "error"
            state["error"] = "Expected screening questions not found"
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"Error loading existing screening: {str(e)}"
        print(f"[workflow] Error loading screening for job_id={state['job_id']}: {e}")
    return state

# Node to load existing final picks
def load_existing_final_node(state: RecruitmentState) -> RecruitmentState:
    """Load existing final picks if available."""
    try:
        existing_final = get_final_picks(state["job_id"], PROCESSED_DIR)
        if existing_final:
            state["final_picks"] = existing_final
            state["status"] = "final_loaded"
            print(f"[workflow] Loaded existing final picks for job_id={state['job_id']}")
        else:
            state["status"] = "error"
            state["error"] = "Expected final picks not found"
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"Error loading existing final picks: {str(e)}"
        print(f"[workflow] Error loading final picks for job_id={state['job_id']}: {e}")
    return state

# Node to load call data
def calls_node(state: RecruitmentState) -> RecruitmentState:
    """Load call data for the given job_id."""
    try:
        state["call_data"] = get_call_data(state["job_id"], PROCESSED_DIR)
        state["status"] = "calls_loaded"
        print(f"[workflow] Loaded {len(state['call_data'])} call entries for job_id={state['job_id']}")
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"Error loading call data: {str(e)}"
        print(f"[workflow] Error loading calls for job_id={state['job_id']}: {e}")
    return state

# Build the workflow graph
def build_workflow() -> StateGraph:
    workflow = StateGraph(RecruitmentState)

    # Define nodes
    workflow.add_node("load_job", load_job_node)
    workflow.add_node("extract_cvs", extract_cvs_node)
    workflow.add_node("load_existing_shortlist", load_existing_shortlist_node)
    workflow.add_node("shortlist", shortlist_node)
    workflow.add_node("load_existing_screening", load_existing_screening_node)  
    workflow.add_node("screening", screening_node)
    workflow.add_node("calls", calls_node)
    workflow.add_node("load_existing_final", load_existing_final_node)
    workflow.add_node("final_picks", final_picks_node)

    # Define edges
    workflow.set_entry_point("load_job")
    workflow.add_edge("load_job", "extract_cvs")
    
    # CV count check with proper branching
    workflow.add_conditional_edges(
        "extract_cvs",
        check_cv_count,
        {
            "shortlist": "shortlist", 
            "load_existing_shortlist": "load_existing_shortlist",
            "wait": END
        }
    )
    
    # After shortlisting, check screening
    workflow.add_conditional_edges(
        "shortlist",
        check_screening_exists,
        {
            "screening": "screening", 
            "load_existing_screening": "load_existing_screening",
            "wait": END
        }
    )
    
    # After loading existing shortlist, check screening
    workflow.add_conditional_edges(
        "load_existing_shortlist", 
        check_screening_exists,
        {
            "screening": "screening",
            "load_existing_screening": "load_existing_screening", 
            "wait": END
        }
    )
    
    # After screening, go to calls
    workflow.add_edge("screening", "calls")
    workflow.add_edge("load_existing_screening", "calls")
    
    # After calls, check if ready for final picks
    workflow.add_conditional_edges(
        "calls",
        check_calls_done,
        {
            "final_picks": "final_picks",
            "load_existing_final": "load_existing_final", 
            "wait": END
        }
    )
    
    # End workflow
    workflow.add_edge("final_picks", END)
    workflow.add_edge("load_existing_final", END)

    return workflow.compile()

# Export the compiled workflow
app = build_workflow()