"""
Extraction Tools
Handles retrieval of extracted CV data for job-specific processing.
Filters and formats CV data based on job ID requirements.
"""

import json
from pathlib import Path
from typing import List, Dict, Any


def get_extracted_cvs_for_job(job_id: str, processed_dir: Path, job_id_to_title: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Retrieve list of extracted CV data for a specific job ID.
    
    Searches through processed directory for CV files matching the job ID pattern
    and returns their extracted data along with filename information.
    
    Args:
        job_id: Unique identifier for the job
        processed_dir: Directory containing processed CV JSON files
        job_id_to_title: Mapping of job IDs to job titles (for validation)
        
    Returns:
        List[Dict]: List of CV entries with format:
                   [{"filename": str, "data": dict}, ...]
                   Returns empty list if no CVs found or on error
    """
    cvs = []
    
    # Validate inputs
    if not processed_dir.exists():
        print(f"[get_extracted_cvs_for_job] Processed directory does not exist: {processed_dir}")
        return []
        
    if not job_id:
        print("[get_extracted_cvs_for_job] Empty job_id provided")
        return []
    
    try:
        # Iterate through all files in processed directory
        for file_path in processed_dir.iterdir():
            # Skip non-files and non-JSON files
            if not file_path.is_file() or not file_path.name.endswith('.json'):
                continue
            
            # Skip system files (shortlist, screening, calls, final)
            if any(file_path.name.startswith(prefix) for prefix in ['shortlist_', 'screening_', 'calls_', 'final_']):
                continue
                
            # Parse filename to extract job_id and CV filename
            filename_parts = file_path.name.split('_', 1)
            if len(filename_parts) != 2:
                print(f"[get_extracted_cvs_for_job] Skipping file with invalid format: {file_path.name}")
                continue
                
            file_job_id, cv_filename_with_ext = filename_parts
            
            # Check if this file belongs to the requested job
            if file_job_id != str(job_id):
                continue
            
            try:
                # Load and parse CV data
                with open(file_path, "r", encoding="utf-8") as json_file:
                    cv_data = json.load(json_file)
                    
                # Remove .json extension from filename for consistency
                cv_filename = cv_filename_with_ext[:-5] if cv_filename_with_ext.endswith('.json') else cv_filename_with_ext
                
                # Add to results
                cvs.append({
                    "filename": cv_filename,
                    "data": cv_data
                })
                
                print(f"[get_extracted_cvs_for_job] Loaded CV: {cv_filename}")
                
            except json.JSONDecodeError as e:
                print(f"[get_extracted_cvs_for_job] Invalid JSON in {file_path.name}: {e}")
                continue
                
            except Exception as e:
                print(f"[get_extracted_cvs_for_job] Error reading {file_path.name}: {e}")
                continue
        
        print(f"[get_extracted_cvs_for_job] Found {len(cvs)} CVs for job_id={job_id}")
        return cvs
        
    except Exception as e:
        print(f"[get_extracted_cvs_for_job] Error processing directory {processed_dir}: {e}")
        return []