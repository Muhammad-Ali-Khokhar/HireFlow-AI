"""
Shortlist Tools
Handles saving and retrieving shortlisted candidates for job positions.
Manages the shortlist data lifecycle including persistence and retrieval operations.
"""

import json
from pathlib import Path
from typing import List, Dict, Any


def save_shortlist(job_id: str, shortlisted: List[Dict[str, Any]], processed_dir: Path) -> str:
    """
    Save the shortlist for a job as a JSON file.
    
    Args:
        job_id: Unique identifier for the job
        shortlisted: List of shortlisted candidate dictionaries
        processed_dir: Directory to save processed data files
        
    Returns:
        str: Path to the saved shortlist file
        
    Raises:
        Exception: If save operation fails
    """
    # Validate inputs
    if not job_id:
        raise ValueError("job_id cannot be empty")
        
    if not isinstance(shortlisted, list):
        raise ValueError(f"shortlisted must be a list, got {type(shortlisted)}")
    
    try:
        # Ensure processed directory exists
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Construct shortlist file path
        shortlist_path = processed_dir / f"shortlist_{job_id}.json"
        
        # Save shortlist data with proper formatting
        with open(shortlist_path, "w", encoding="utf-8") as f:
            json.dump(shortlisted, f, ensure_ascii=False, indent=2)
            
        print(f"[save_shortlist] Saved {len(shortlisted)} candidates to {shortlist_path}")
        return str(shortlist_path)
        
    except Exception as e:
        error_msg = f"Error saving shortlist for job_id={job_id}: {e}"
        print(f"[save_shortlist] {error_msg}")
        raise Exception(error_msg)


def get_shortlist(job_id: str, processed_dir: Path) -> List[Dict[str, Any]]:
    """
    Retrieve shortlisted candidates for a specific job ID.
    
    Args:
        job_id: Unique identifier for the job
        processed_dir: Directory containing processed data files
        
    Returns:
        List[Dict]: List of shortlisted candidate dictionaries
                   Returns empty list if file doesn't exist or has errors
    """
    # Validate inputs
    if not job_id:
        print("[get_shortlist] Empty job_id provided")
        return []
        
    if not processed_dir.exists():
        print(f"[get_shortlist] Processed directory does not exist: {processed_dir}")
        return []
    
    # Construct shortlist file path
    shortlist_path = processed_dir / f"shortlist_{job_id}.json"
    
    # Check if shortlist file exists
    if not shortlist_path.exists():
        print(f"[get_shortlist] No shortlist found for job_id={job_id}")
        return []
    
    try:
        # Read and parse shortlist data
        with open(shortlist_path, "r", encoding="utf-8") as f:
            shortlist_data = json.load(f)
            
        # Validate data format
        if not isinstance(shortlist_data, list):
            print(f"[get_shortlist] Invalid shortlist format in {shortlist_path}: expected list, got {type(shortlist_data)}")
            return []
            
        print(f"[get_shortlist] Loaded {len(shortlist_data)} shortlisted candidates for job_id={job_id}")
        return shortlist_data
        
    except json.JSONDecodeError as e:
        print(f"[get_shortlist] Invalid JSON in {shortlist_path}: {e}")
        return []
        
    except Exception as e:
        print(f"[get_shortlist] Error reading shortlist for job_id={job_id}: {e}")
        return []