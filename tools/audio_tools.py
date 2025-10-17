"""
Audio Tools
Handles audio file processing including format conversion and speech-to-text transcription.
Provides tools for converting audio files and formatting transcripts for interview analysis.
"""

import os
import json
from pathlib import Path
import speech_recognition as sr
from pydub import AudioSegment
from langchain_core.prompts import ChatPromptTemplate
from typing import Optional


def convert_mp3_to_wav(mp3_path: str) -> str:
    """
    Convert MP3 file to WAV format and return the WAV file path.
    
    Args:
        mp3_path: Path to the MP3 file
        
    Returns:
        str: Path to the converted WAV file
        
    Raises:
        Exception: If conversion fails
    """
    try:
        wav_path = os.path.splitext(mp3_path)[0] + ".wav"
        print(f"[convert_mp3_to_wav] Converting {mp3_path} to {wav_path}")
        
        # Load and convert audio
        sound = AudioSegment.from_mp3(mp3_path)
        sound.export(wav_path, format="wav")
        
        print(f"[convert_mp3_to_wav] Successfully converted to {wav_path}")
        return wav_path
        
    except Exception as e:
        error_msg = f"Error converting MP3 to WAV: {str(e)}"
        print(f"[convert_mp3_to_wav] {error_msg}")
        raise Exception(error_msg)


def transcribe_audio_file(file_path: str) -> str:
    """
    Transcribe audio file (WAV format) to text using Google Speech Recognition.
    
    Args:
        file_path: Path to the WAV audio file
        
    Returns:
        str: Transcribed text or error message
    """
    try:
        recognizer = sr.Recognizer()
        
        print(f"[transcribe_audio_file] Processing: {file_path}")
        
        # Validate file exists
        if not os.path.exists(file_path):
            return "[ERROR] Audio file not found"
        
        # Validate file is WAV format
        if not file_path.lower().endswith(".wav"):
            return "[ERROR] File must be in WAV format"
        
        audio = AudioSegment.from_wav(file_path)
        chunk_duration = 30 * 1000 # 30 seconds in milliseconds
        transcriptions = []

        for i, start_ms in enumerate(range(0, len(audio), chunk_duration)):
            end_ms = min(start_ms + chunk_duration, len(audio))
            chunk = audio[start_ms:end_ms]

            # Save chunk temporarily
            chunk_path = f"temp_chunk_{i}.wav"
            chunk.export(chunk_path, format="wav")

            # Transcribe chunk
            with sr.AudioFile(chunk_path) as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = recognizer.record(source)
                try:
                    text = recognizer.recognize_google(audio_data)
                    transcriptions.append(text)
                    print(f"[transcribe_audio_file] Chunk {i+1} processed")
                except sr.UnknownValueError:
                    print(f"[transcribe_audio_file] Warning: Could not understand chunk {i+1}")
                except sr.RequestError as e:
                    print(f"[transcribe_audio_file] Error: Could not request results for chunk {i+1}: {e}")

            # Clean up temporary chunk file
            os.remove(chunk_path)

        # Join all transcriptions
        full_text = " ".join(transcriptions)
        if full_text.strip():
            print(f"[transcribe_audio_file] Successfully transcribed {len(full_text)} characters")
            return full_text
        else:
            return "[ERROR] Could not understand the audio. Please ensure the audio is clear and try again."
        
    except Exception as e:
        error_msg = f"[Error] Audio processing failed: {str(e)}"
        print(f"[transcribe_audio_file] {error_msg}")
        return error_msg


def format_transcript_with_llm(llm, raw_transcript: str) -> Optional[str]:
    """
    Format raw transcript text into structured interview format using LLM.
    
    Args:
        llm: Initialized LangChain LLM instance
        raw_transcript: Raw transcribed text from audio
        
    Returns:
        str: Formatted transcript in interview format or None if failed
    """
    try:
        prompt = ChatPromptTemplate.from_template(
            """You are an expert at formatting interview transcripts. Given the raw transcript text below, format it into a structured interview format with clear separation between interviewer questions and candidate responses.

Raw Transcript:
{raw_transcript}

Format the transcript using this structure:
interview:
question 1: [Extract or infer the first question asked]
candidate: [Candidate's response to question 1]

question 2: [Extract or infer the second question asked]  
candidate: [Candidate's response to question 2]

[Continue for all questions and responses...]

Guidelines:
1. Identify where questions end and responses begin
2. If questions are not explicitly stated, infer them from context
3. Clean up filler words and false starts while preserving meaning
4. Maintain professional tone
5. If the transcript is unclear or too short, do your best to structure what's available
6. Start directly with "interview:" and do not include any preamble or explanation

Return ONLY the formatted transcript, nothing else."""
        )
        
        # Invoke LLM to format transcript
        response = llm.invoke(prompt.format(raw_transcript=raw_transcript))
        formatted_transcript = response.content.strip()
        
        # Validate response starts with "interview:"
        if not formatted_transcript.lower().startswith("interview:"):
            print("[format_transcript_with_llm] Warning: LLM response doesn't start with 'interview:'")
            formatted_transcript = "interview:\n" + formatted_transcript
        
        print(f"[format_transcript_with_llm] Successfully formatted transcript ({len(formatted_transcript)} characters)")
        return formatted_transcript
        
    except Exception as e:
        print(f"[format_transcript_with_llm] Error formatting transcript: {e}")
        return None


def cleanup_temp_files(file_path: str) -> None:
    """
    Clean up temporary audio files created during processing.
    
    Args:
        file_path: Path to the file to clean up
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"[cleanup_temp_files] Removed temporary file: {file_path}")
    except Exception as e:
        print(f"[cleanup_temp_files] Warning: Could not remove {file_path}: {e}")


def get_file_type(file_path: str) -> str:
    """
    Determine the file type based on extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        str: File type ('text', 'mp3', 'wav', 'unknown')
    """
    extension = Path(file_path).suffix.lower()
    
    if extension == ".txt":
        return "text"
    elif extension == ".mp3":
        return "mp3"
    elif extension == ".wav":
        return "wav"
    else:
        return "unknown"


def validate_audio_file(file_path: str) -> tuple[bool, str]:
    """
    Validate if the audio file can be processed.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    try:
        file_path = Path(file_path)
        
        # Check if file exists
        if not file_path.exists():
            return False, "File does not exist"
        
        # Check file size (limit to 25MB for reasonable processing)
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > 25:
            return False, f"File too large: {file_size_mb:.1f}MB. Maximum size is 25MB"
        
        # Check file extension
        extension = file_path.suffix.lower()
        if extension not in [".mp3", ".wav"]:
            return False, f"Unsupported audio format: {extension}. Only .mp3 and .wav are supported"
        
        return True, "File is valid"
        
    except Exception as e:
        return False, f"File validation error: {str(e)}"