import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from typing import Dict, Any
import sys
import speech_recognition as sr
from pydub import AudioSegment

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from app.state import RecruitmentState
from tools.audio_tools import convert_mp3_to_wav, transcribe_audio_file, format_transcript_with_llm

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("[Agent3 Error] GROQ_API_KEY not found")

def audio_processing_node(state: RecruitmentState) -> RecruitmentState:
    """
    LangGraph node to process audio files and generate formatted transcripts.
    Handles both direct text files and audio files (mp3/wav).
    Updates the state with processed transcript or an error.
    """
    print(f"[Agent3] Starting audio processing for job_id={state['job_id']}")
    
    try:
        # Extract required data from state
        job_id = state["job_id"]
        file_path = state.get("audio_file_path")
        filename = state.get("candidate_filename")
        
        if not file_path or not filename:
            state["status"] = "error"
            state["error"] = "Missing file path or candidate filename"
            print(f"[Agent3 Error] {state['error']}")
            return state
        
        file_path = Path(file_path)
        if not file_path.exists():
            state["status"] = "error"
            state["error"] = f"File not found: {file_path}"
            print(f"[Agent3 Error] {state['error']}")
            return state
        
        # Determine file type and process accordingly
        file_extension = file_path.suffix.lower()
        transcript_text = ""
        
        if file_extension == ".txt":
            # Handle text file directly
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    transcript_text = f.read().strip()
                print(f"[Agent3] Loaded text transcript from {file_path}")
            except Exception as e:
                state["status"] = "error"
                state["error"] = f"Error reading text file: {str(e)}"
                print(f"[Agent3 Error] {state['error']}")
                return state
                
        elif file_extension in [".mp3", ".wav"]:
            # Handle audio file
            try:
                # Convert mp3 to wav if necessary
                if file_extension == ".mp3":
                    print(f"[Agent3] Converting MP3 to WAV: {file_path}")
                    wav_path = convert_mp3_to_wav(str(file_path))
                    audio_file_path = wav_path
                else:
                    audio_file_path = str(file_path)
                
                # Transcribe audio to text
                print(f"[Agent3] Transcribing audio file: {audio_file_path}")
                raw_transcript = transcribe_audio_file(audio_file_path)
                
                if raw_transcript.startswith("[ERROR]"):
                    state["status"] = "error"
                    state["error"] = f"Audio transcription failed: {raw_transcript}"
                    print(f"[Agent3 Error] {state['error']}")
                    return state
                
                # Format transcript using LLM
                print(f"[Agent3] Formatting transcript with LLM")
                try:
                    llm = ChatGroq(
                        model="llama-3.3-70b-versatile",
                        api_key=GROQ_API_KEY,
                        temperature=0.1,
                        max_tokens=4096
                    )
                except Exception as e:
                    state["status"] = "error"
                    state["error"] = f"Failed to initialize LLM: {str(e)}"
                    print(f"[Agent3 Error] {state['error']}")
                    return state
                
                transcript_text = format_transcript_with_llm(llm, raw_transcript)
                
                if not transcript_text:
                    state["status"] = "error"
                    state["error"] = "Failed to format transcript with LLM"
                    print(f"[Agent3 Error] {state['error']}")
                    return state
                    
                print(f"[Agent3] Successfully formatted transcript")
                
            except Exception as e:
                state["status"] = "error"
                state["error"] = f"Error processing audio file: {str(e)}"
                print(f"[Agent3 Error] {state['error']}")
                return state
        else:
            state["status"] = "error"
            state["error"] = f"Unsupported file type: {file_extension}. Only .txt, .mp3, and .wav files are supported"
            print(f"[Agent3 Error] {state['error']}")
            return state
        
        # Validate transcript content
        if not transcript_text or len(transcript_text.strip()) < 10:
            state["status"] = "error"
            state["error"] = "Transcript is too short or empty"
            print(f"[Agent3 Error] {state['error']}")
            return state
        
        # Update state with processed transcript
        state["processed_transcript"] = transcript_text
        state["status"] = "audio_processed"
        
        print(f"[Agent3] Successfully processed {file_extension} file for candidate {filename}")
        print(f"[Agent3] Transcript length: {len(transcript_text)} characters")
        
        return state
        
    except Exception as e:
        state["status"] = "error"
        state["error"] = f"Unexpected error in audio_processing_node: {str(e)}"
        print(f"[Agent3 Error] {state['error']}")
        return state