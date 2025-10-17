"""
Calls Tools
Handles storage and retrieval of call data including status and transcripts for job candidates.
Manages the call data lifecycle from initial state to completion with transcripts.
"""

import json
from pathlib import Path
from typing import List, Dict, Any


def get_call_data(job_id: str, processed_dir: Path) -> List[Dict[str, Any]]:
    """
    Retrieve call data (status and transcripts) for a given job ID.
    
    Args:
        job_id: Unique identifier for the job
        processed_dir: Directory containing processed data files
        
    Returns:
        List[Dict]: List of call entries with status and transcript data
                   Returns empty list if file doesn't exist or has errors
    """
    call_file = processed_dir / f"calls_{job_id}.json"
    
    # Check if call data file exists
    if not call_file.exists():
        print(f"[get_call_data] No call data found for job_id={job_id}")
        return []
    
    try:
        # Read and parse the call data file
        with open(call_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # Validate data is a list
        if not isinstance(data, list):
            print(f"[get_call_data] Invalid data format in {call_file}: expected list, got {type(data)}")
            return []
            
        print(f"[get_call_data] Loaded {len(data)} call entries for job_id={job_id}")
        return data
        
    except json.JSONDecodeError as e:
        print(f"[get_call_data] Invalid JSON in {call_file}: {e}")
        return []
        
    except Exception as e:
        print(f"[get_call_data] Error reading call data for job_id={job_id}: {e}")
        return []


def save_call_data(job_id: str, call_data: List[Dict[str, Any]], processed_dir: Path) -> None:
    """
    Save call data (status and transcripts) for a given job ID.
    
    Args:
        job_id: Unique identifier for the job
        call_data: List of call entries to save
        processed_dir: Directory to save processed data files
        
    Raises:
        Exception: If save operation fails
    """
    call_file = processed_dir / f"calls_{job_id}.json"
    
    try:
        # Ensure processed directory exists
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate input data
        if not isinstance(call_data, list):
            raise ValueError(f"call_data must be a list, got {type(call_data)}")
            
        # Save call data with proper formatting
        with open(call_file, "w", encoding="utf-8") as f:
            json.dump(call_data, f, indent=2, ensure_ascii=False)
            
        print(f"[save_call_data] Saved call data to {call_file}")
        
    except Exception as e:
        error_msg = f"Error saving call data for job_id={job_id}: {e}"
        print(f"[save_call_data] {error_msg}")
        raise Exception(error_msg)