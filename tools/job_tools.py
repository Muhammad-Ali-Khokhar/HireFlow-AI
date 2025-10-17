"""
Job Tools
Handles retrieval of job details and information from the jobs configuration file.
Provides centralized access to job data for various recruitment process components.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


def get_job_details(job_id: str, jobs_file: Path) -> Optional[Dict[str, Any]]:
    """
    Retrieve job details for a specific job ID.
    
    Args:
        job_id: Unique identifier for the job
        jobs_file: Path to the jobs configuration JSON file
        
    Returns:
        Dict: Job details dictionary if found, None if not found
              Job dict contains keys like: id, title, description, requirements, etc.
    """
    # Validate inputs
    if not job_id:
        print("[get_job_details] Empty job_id provided")
        return None
        
    if not jobs_file or not jobs_file.exists():
        print(f"[get_job_details] Jobs file not found: {jobs_file}")
        return None
    
    try:
        # Load jobs data from file
        with open(jobs_file, "r", encoding="utf-8") as f:
            jobs_data = json.load(f)
            
        # Validate jobs data format
        if not isinstance(jobs_data, list):
            print(f"[get_job_details] Invalid jobs file format: expected list, got {type(jobs_data)}")
            return None
        
        # Search for matching job ID
        for job in jobs_data:
            if not isinstance(job, dict):
                print(f"[get_job_details] Skipping invalid job entry: {job}")
                continue
                
            # Compare job IDs as strings to handle type variations
            if str(job.get("id", "")) == str(job_id):
                print(f"[get_job_details] Found job: {job.get('title', 'Unknown')} (ID: {job_id})")
                return job
        
        # Job not found
        print(f"[get_job_details] Job not found for job_id={job_id}")
        return None
        
    except json.JSONDecodeError as e:
        print(f"[get_job_details] Invalid JSON in jobs file {jobs_file}: {e}")
        return None
        
    except Exception as e:
        print(f"[get_job_details] Error reading jobs file {jobs_file}: {e}")
        return None