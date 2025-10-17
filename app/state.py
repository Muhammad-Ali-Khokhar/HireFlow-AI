from typing import TypedDict, List, Dict, Any, Optional

class RecruitmentState(TypedDict):
    job_id: str
    job: Optional[Dict[str, Any]]  # Job details from jobs.json
    cvs: List[Dict[str, Any]]  # Extracted CVs
    shortlist: List[Dict[str, Any]]  # Shortlisted candidates
    screening_questions: List[Dict[str, Any]]  # Screening questions per candidate
    call_data: List[Dict[str, Any]]  # Call status and transcripts
    final_picks: List[Dict[str, Any]]  # Final candidates with interview times
    status: str  # Tracks workflow stage (e.g., "extracted", "shortlisted", "calls_pending")
    error: Optional[str]  # Stores any error messages
    audio_file_path: Optional[str]  # Path to uploaded audio/text file
    candidate_filename: Optional[str]  # Filename of the candidate
    processed_transcript: Optional[str]  # Processed transcript text