import json
from pathlib import Path
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import base64
from email.mime.text import MIMEText
from langchain_core.tools import tool
from typing import List, Dict, Any

def get_call_data(job_id: str, processed_dir: Path) -> List[Dict[str, Any]]:
    """Return call data (status and transcripts) for a given job_id."""
    call_file = processed_dir / f"calls_{job_id}.json"
    if not call_file.exists():
        print(f"[get_call_data] No call data found for job_id={job_id}")
        return []
    try:
        with open(call_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[get_call_data] Loaded {len(data)} call entries for job_id={job_id}")
        return data
    except json.JSONDecodeError as e:
        print(f"[get_call_data] Invalid JSON in {call_file}: {e}")
        return []
    except Exception as e:
        print(f"[get_call_data] Error reading call data: {e}")
        return []

@tool
def save_final_picks(job_id: str, final_picks: List[Dict], output_dir: str) -> bool:
    """Save final picks with interview schedules for a given job_id."""
    try:
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)
        final_file = output_dir_path / f"final_{job_id}.json"
        
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(final_picks, f, indent=2, ensure_ascii=False)
        print(f"[save_final_picks] Saved final picks to {final_file}")
        return True
    except Exception as e:
        print(f"[save_final_picks] Error saving final picks for job_id={job_id}: {e}")
        return False

def get_final_picks(job_id: str, processed_dir: Path) -> List[Dict[str, Any]]:
    """Return final picks data for a given job_id."""
    final_file = processed_dir / f"final_{job_id}.json"
    if not final_file.exists():
        print(f"[get_final_picks] No final picks found for job_id={job_id}")
        return []
    try:
        with open(final_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[get_final_picks] Loaded {len(data)} final picks for job_id={job_id}")
        return data
    except json.JSONDecodeError as e:
        print(f"[get_final_picks] Invalid JSON in {final_file}: {e}")
        return []
    except Exception as e:
        print(f"[get_final_picks] Error reading final picks: {e}")
        return []

def get_calendar_service():
    """Return Google Calendar API service."""
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    try:
        creds = None
        token_path = 'token.json'
        if os.path.exists(token_path):
            with open(token_path, 'r') as token_file:
                token_data = json.load(token_file)
                print(f"[get_calendar_service] Loaded token.json with scopes: {token_data.get('scopes', [])}")
                if 'refresh_token' not in token_data:
                    print("[get_calendar_service] Missing refresh_token in token.json")
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[get_calendar_service] Refreshing expired token")
                creds.refresh(Request())
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
            else:
                print("[get_calendar_service] No valid token, re-authenticating")
                if not os.path.exists('credentials.json'):
                    print("[get_calendar_service] credentials.json not found")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                flow.redirect_uri = 'http://localhost:8080/'  # Match auth_gmail.py
                creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"[get_calendar_service] Error initializing calendar service: {e}")
        return None

def get_gmail_service():
    """Return Gmail API service."""
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    try:
        creds = None
        token_path = 'token.json'
        if os.path.exists(token_path):
            with open(token_path, 'r') as token_file:
                token_data = json.load(token_file)
                print(f"[get_gmail_service] Loaded token.json with scopes: {token_data.get('scopes', [])}")
                if 'refresh_token' not in token_data:
                    print("[get_gmail_service] Missing refresh_token in token.json")
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[get_gmail_service] Refreshing expired token")
                creds.refresh(Request())
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
            else:
                print("[get_gmail_service] No valid token, re-authenticating")
                if not os.path.exists('credentials.json'):
                    print("[get_gmail_service] credentials.json not found")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                flow.redirect_uri = 'http://localhost:8080/'  # Match auth_gmail.py
                creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        print(f"[get_gmail_service] Error initializing Gmail service: {e}")
        return None

def send_interview_invite(job_id: str, job_title: str, candidate_name: str, candidate_email: str, interview_time: datetime, cv_filename: str):
    """Send an interview invite email to HR and the candidate."""
    service = get_gmail_service()
    if not service:
        print("[send_interview_invite] Failed to get Gmail service")
        return False
    
    hr_email = "youremail@gmail.com" # Replace with actual HR email
    formatted_time = interview_time.strftime("%A, %B %d, %Y, %I:%M %p PKT")
    subject = f"Interview Scheduled: {candidate_name} for {job_title}"
    
    body = f"""Dear HR Team,

An interview has been scheduled for the following candidate:

**Position**: {job_title} (Job ID: {job_id})
**Candidate**: {candidate_name}
**Interview Time**: {formatted_time}
**CV**: Available at http://localhost:8080/cvs/{job_id}_{cv_filename}

Please prepare for the interview and review the candidate's CV. If you have any questions, feel free to contact the recruitment team.

Best regards,
Hiredroid Recruitment System
"""
    
    # Create email message
    message = MIMEText(body)
    message['to'] = hr_email
    if candidate_email:
        message['cc'] = candidate_email
    message['from'] = 'youremail@gmail.com' # Replace with actual sender email
    message['subject'] = subject
    
    # Encode the message
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    try:
        service.users().messages().send(userId='me', body={'raw': raw_message}).execute()
        print(f"[send_interview_invite] Email sent to {hr_email} and CC to {candidate_email if candidate_email else 'None'}")
        return True
    except Exception as e:
        print(f"[send_interview_invite] Error sending email for {candidate_name}: {e}")
        return False

def schedule_interview(job_id: str, job_title: str, cv_filename: str, candidate_name: str, candidate_email: str, start_time: datetime) -> datetime:
    """Schedule an interview in Google Calendar during working hours (Mon-Fri, 1 PM-10 PM PKT)."""
    service = get_calendar_service()
    if not service:
        print("[schedule_interview] Failed to get calendar service")
        return None
    
    # Ensure PKT timezone
    pkt = ZoneInfo("Asia/Karachi")
    start_time = start_time.astimezone(pkt)
    
    # Find next available 30-minute slot (Mon-Fri, 1 PM-10 PM)
    current_time = start_time
    max_attempts = 50  # Increased attempts to find a slot
    slot_duration = timedelta(minutes=30)  # Interview duration
    break_duration = timedelta(minutes=15)  # Break between interviews
    
    for attempt in range(max_attempts):
        # Skip weekends - move to next Monday 1 PM
        if current_time.weekday() >= 5:  # Saturday or Sunday
            days_until_monday = 7 - current_time.weekday()
            current_time = current_time.replace(hour=13, minute=0, second=0, microsecond=0)
            current_time += timedelta(days=days_until_monday)
            continue
        
        # Ensure within working hours (1 PM-10 PM)
        if current_time.hour < 13:
            current_time = current_time.replace(hour=13, minute=0, second=0, microsecond=0)
        elif current_time.hour >= 22 or (current_time.hour == 21 and current_time.minute >= 30):
            # After 9:30 PM (no room for 30-min slot), move to next day 1 PM
            current_time = current_time.replace(hour=13, minute=0, second=0, microsecond=0)
            current_time += timedelta(days=1)
            continue
        
        # Check for conflicts
        end_time = current_time + slot_duration
        
        try:
            events_result = service.events().list(
                calendarId='primary',
                timeMin=current_time.isoformat(),
                timeMax=end_time.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Check if there are any conflicting events
            has_conflict = False
            for event in events:
                # Skip cancelled events
                if event.get('status') == 'cancelled':
                    continue
                    
                # Check for actual time overlap
                event_start = event.get('start', {})
                event_end = event.get('end', {})
                
                if event_start.get('dateTime') and event_end.get('dateTime'):
                    event_start_dt = datetime.fromisoformat(event_start['dateTime'].replace('Z', '+00:00'))
                    event_end_dt = datetime.fromisoformat(event_end['dateTime'].replace('Z', '+00:00'))
                    
                    # Convert to PKT for comparison
                    event_start_dt = event_start_dt.astimezone(pkt)
                    event_end_dt = event_end_dt.astimezone(pkt)
                    
                    # Check for overlap: events overlap if one starts before the other ends
                    if (current_time < event_end_dt and end_time > event_start_dt):
                        has_conflict = True
                        print(f"[schedule_interview] Conflict found at {current_time} with existing event: {event.get('summary', 'Unknown')}")
                        break
            
            # If no conflicts, create the event
            if not has_conflict:
                event = {
                    'summary': f'Interview: {candidate_name} for {job_title}',
                    'description': (
                        f'Interview with {candidate_name} for the {job_title} position (Job ID: {job_id}).\n'
                        f'Please review the candidate\'s CV at http://localhost:8080/cvs/{job_id}_{cv_filename}.\n'
                        f'Contact the recruitment team for any additional details.'
                    ),
                    'start': {
                        'dateTime': current_time.isoformat(),
                        'timeZone': 'Asia/Karachi',
                    },
                    'end': {
                        'dateTime': end_time.isoformat(),
                        'timeZone': 'Asia/Karachi',
                    },
                    'attendees': [
                        {'email': 'youremail@gmail.com'}, # Replace with actual HR email
                        {'email': candidate_email} if candidate_email else None
                    ]
                }
                
                # Remove None attendees
                event['attendees'] = [attendee for attendee in event['attendees'] if attendee]
                
                try:
                    created_event = service.events().insert(calendarId='primary', body=event).execute()
                    print(f"[schedule_interview] Successfully scheduled interview for {candidate_name} at {current_time}")
                    
                    # Send email invite
                    send_interview_invite(job_id, job_title, candidate_name, candidate_email, current_time, cv_filename)
                    return current_time
                    
                except Exception as e:
                    print(f"[schedule_interview] Error creating event for {candidate_name}: {e}")
                    return None
        
        except Exception as e:
            print(f"[schedule_interview] Error checking calendar for {candidate_name}: {e}")
            return None
        
        # Move to next 30-minute slot + 15-minute break
        current_time += slot_duration + break_duration
    
    print(f"[schedule_interview] No available slot found for {candidate_name} after {max_attempts} attempts")
    return None