from fastapi import FastAPI, UploadFile, File
from backend.agent import run_agents
from backend.speech_to_text import transcribe_audio
from backend.text_to_speech import speak_text
from backend.utils import save_audio
from fastapi.responses import StreamingResponse

app = FastAPI()

@app.post("/process_audio/")
async def process_audio(file: UploadFile = File(...)):
    path = save_audio(file.file)
    text = transcribe_audio(path)
    response = run_agents(text)
    audio_stream = speak_text(response)
    return StreamingResponse(audio_stream, media_type="audio/mpeg")
