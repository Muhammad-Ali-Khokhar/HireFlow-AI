import json
from pathlib import Path
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import List, Dict, Any

class ExtractedCVsInput(BaseModel):
    job_id: str = Field(..., description="The ID of the job")
    processed_dir: str = Field(..., description="Directory containing processed CV JSON files")
    job_id_to_title: Dict[str, str] = Field(..., description="Mapping of job IDs to titles")

class ShortlistInput(BaseModel):
    job_id: str = Field(..., description="The ID of the job")
    shortlist: List[Dict] = Field(..., description="List of shortlisted candidates")
    output_dir: str = Field(..., description="Directory to save the shortlist")

class ScreeningQuestionsInput(BaseModel):
    job_id: str = Field(..., description="The ID of the job")
    questions: List[Dict] = Field(..., description="List of screening questions")
    output_dir: str = Field(..., description="Directory to save the questions")

class FinalPicksInput(BaseModel):
    job_id: str = Field(..., description="The ID of the job")
    final_picks: List[Dict] = Field(..., description="List of final picks")
    output_dir: str = Field(..., description="Directory to save the final picks")

@tool(args_schema=ExtractedCVsInput)
def get_extracted_cvs_for_job(job_id: str, processed_dir: str, job_id_to_title: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Retrieve extracted CV data for a specific job from the processed directory.
    """
    try:
        processed_dir = Path(processed_dir)
        cv_data = []
        for f in processed_dir.glob(f"{job_id}_*.json"):
            try:
                with open(f, "r", encoding="utf-8") as file:
                    data = json.load(file)
                filename = f.name[len(job_id)+1:-5]
                cv_data.append({
                    "filename": filename,
                    "data": data
                })
                print(f"[get_extracted_cvs_for_job] Loaded CV: {filename}")
            except Exception as e:
                print(f"[get_extracted_cvs_for_job] Error loading {f}: {e}")
        print(f"[get_extracted_cvs_for_job] Found {len(cv_data)} CVs for job_id={job_id}")
        return cv_data
    except Exception as e:
        print(f"[get_extracted_cvs_for_job] Error: {e}")
        return []

@tool(args_schema=ShortlistInput)
def save_shortlist(input_data: Dict[str, Any]) -> bool:
    """
    Save the shortlist data to a JSON file in the specified directory.
    """
    try:
        job_id = input_data["job_id"]
        shortlist = input_data["shortlist"]
        output_dir = Path(input_data["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"shortlist_{job_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(shortlist, f, ensure_ascii=False, indent=2)
        print(f"[save_shortlist] Saved shortlist for job_id={job_id} to {output_file}")
        return True
    except Exception as e:
        print(f"[save_shortlist] Error saving shortlist for job_id={job_id}: {e}")
        return False

@tool(args_schema=ScreeningQuestionsInput)
def save_screening_questions(input_data: Dict[str, Any]) -> bool:
    """
    Save the screening questions to a JSON file.
    """
    try:
        job_id = input_data["job_id"]
        questions = input_data["questions"]
        output_dir = Path(input_data["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"screening_{job_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(questions, f, ensure_ascii=False, indent=2)
        print(f"[save_screening_questions] Saved screening questions for job_id={job_id} to {output_file}")
        return True
    except Exception as e:
        print(f"[save_screening_questions] Error saving questions for job_id={job_id}: {e}")
        return False

@tool(args_schema=FinalPicksInput)
def save_final_picks(input_data: Dict[str, Any]) -> bool:
    """
    Save the final picks to a JSON file.
    """
    try:
        job_id = input_data["job_id"]
        final_picks = input_data["final_picks"]
        output_dir = Path(input_data["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"final_{job_id}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(final_picks, f, ensure_ascii=False, indent=2)
        print(f"[save_final_picks] Saved final picks for job_id={job_id} to {output_file}")
        return True
    except Exception as e:
        print(f"[save_final_picks] Error saving final picks for job_id={job_id}: {e}")
        return False

@tool
def get_shortlisted_cvs(job_id: str, shortlist_dir: str, processed_dir: str) -> List[Dict[str, Any]]:
    """
    Retrieve shortlisted CVs for a specific job from the processed directory.
    """
    try:
        shortlist_file = Path(shortlist_dir) / f"shortlist_{job_id}.json"
        if not shortlist_file.exists():
            print(f"[get_shortlisted_cvs] No shortlist found for job_id={job_id}")
            return []
        with open(shortlist_file, "r", encoding="utf-8") as f:
            shortlist = json.load(f)
        cv_data = []
        for entry in shortlist:
            cv_file = Path(processed_dir) / f"{job_id}_{entry['filename']}.json"
            if cv_file.exists():
                with open(cv_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cv_data.append({
                    "filename": entry["filename"],
                    "data": data,
                    "reason": entry.get("reason", "")
                })
                print(f"[get_shortlisted_cvs] Loaded CV: {entry['filename']}")
        return cv_data
    except Exception as e:
        print(f"[get_shortlisted_cvs] Error: {e}")
        return []