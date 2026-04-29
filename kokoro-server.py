#!/usr/bin/env python3
"""
KokoroTTS Server - Local Windows Version
FastAPI server providing OpenAI-compatible TTS endpoint using Kokoro-82M model.
"""

import io
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Kokoro imports
from kokoro import KPipeline
import torch

app = FastAPI(
    title="Kokoro TTS Server",
    description="OpenAI-compatible TTS API using Kokoro-82M",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global pipeline
pipeline: Optional[KPipeline] = None

# Available voices
VOICE_MAP = {
    # American female
    "af_bella": "af_bella",
    "af_heart": "af_heart",
    "af_nicole": "af_nicole",
    "af_sarah": "af_sarah",
    "af_sky": "af_sky",
    # American male
    "am_adam": "am_adam",
    "am_echo": "am_echo",
    "am_eric": "am_eric",
    "am_fenrir": "am_fenrir",
    "am_liam": "am_liam",
    "am_michael": "am_michael",
    "am_onyx": "am_onyx",
    "am_puck": "am_puck",
    "am_santa": "am_santa",
    # British female
    "bf_alice": "bf_alice",
    "bf_emma": "bf_emma",
    "bf_isabella": "bf_isabella",
    "bf_lily": "bf_lily",
    # British male
    "bm_daniel": "bm_daniel",
    "bm_fable": "bm_fable",
    "bm_george": "bm_george",
    "bm_lewis": "bm_lewis",
}


class SpeechRequest(BaseModel):
    """OpenAI-compatible speech request."""
    input: str
    voice: str = "af_bella"
    speed: float = 1.0
    model: str = "kokoro-82M"
    response_format: str = "wav"


@app.on_event("startup")
async def startup_event():
    """Initialize the Kokoro pipeline."""
    global pipeline
    print("[KokoroTTS] Initializing KPipeline...")
    print("[KokoroTTS] This may take 2-3 minutes on first run (model download)...")
    
    try:
        # Use CPU (no GPU available)
        pipeline = KPipeline(lang_code='a')
        print("[KokoroTTS] Pipeline initialized successfully!")
        print("[KokoroTTS] Available voices:", list(VOICE_MAP.keys())[:5], "...")
    except Exception as e:
        print(f"[KokoroTTS] Error initializing pipeline: {e}")
        raise


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "pipeline_loaded": pipeline is not None,
        "voices_available": list(VOICE_MAP.keys())
    }


@app.post("/v1/audio/speech")
async def generate_speech(request: SpeechRequest):
    """Generate speech from text."""
    if pipeline is None:
        raise HTTPException(status_code=503, detail="TTS pipeline not initialized")
    
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty")
    
    # Validate voice
    voice = VOICE_MAP.get(request.voice, "af_bella")
    
    try:
        # Create temp file for output
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            output_path = tmp.name
        
        # Generate speech
        print(f"[KokoroTTS] Generating speech for: {request.input[:50]}...")
        print(f"[KokoroTTS] Voice: {voice}, Speed: {request.speed}")
        
        # Generate audio using pipeline
        generator = pipeline(
            request.input,
            voice=voice,
            speed=request.speed,
        )
        
        # Collect all audio segments
        all_audio = []
        for _, _, audio in generator:
            all_audio.append(audio)
        
        if not all_audio:
            raise HTTPException(status_code=500, detail="No audio generated")
        
        # Concatenate audio segments
        import torchaudio
        import torch
        
        if len(all_audio) == 1:
            final_audio = all_audio[0]
        else:
            final_audio = torch.cat(all_audio, dim=0)
        
        # Save to file
        torchaudio.save(output_path, final_audio.unsqueeze(0), 24000)
        
        print(f"[KokoroTTS] Generated audio: {output_path}")
        
        # Return audio file
        return FileResponse(
            output_path,
            media_type="audio/wav",
            filename="speech.wav",
            headers={"X-TTS-Voice": voice}
        )
        
    except Exception as e:
        print(f"[KokoroTTS] Error generating speech: {e}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")


@app.options("/v1/audio/speech")
async def speech_options():
    """Handle OPTIONS request for CORS."""
    return JSONResponse(content={})


if __name__ == "__main__":
    print("=" * 60)
    print("KokoroTTS Server - Local Windows")
    print("=" * 60)
    print("Port: 8880")
    print("Endpoint: POST /v1/audio/speech")
    print("Health: GET /health")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8880)
