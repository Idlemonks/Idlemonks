from fastapi import FastAPI, UploadFile, File
from agent.agent import (run_agents)
from services.speech_to_text import transcribe_audio
from services.text_to_speech import speak_text
from utils.utils import save_audio
from fastapi.responses import StreamingResponse
import requests 

app = FastAPI(title="SOL")


@app.get("/")
def read_root():
    return {"message": "SOL is running!"}

@app.post("/process_audio/")
async def process_audio(file: UploadFile = File(...)):
    path = save_audio(file.file)
    text = transcribe_audio(path)
    response = run_agents(text)
    audio_stream = speak_text(response)
    return StreamingResponse(audio_stream, media_type="audio/mpeg")


def send_audio(filepath):
    with open(filepath, "rb") as f:
        files = {"audio": f}
        response = requests.post("http://localhost:8081/upload-audio", files=files)
    return response.text


@app.post("/query/")
def handle_query(audio_input: bytes):
    text = transcribe_audio(audio_input)
    response = agent.process(text)
    audio_response = synthesize_speech(response)
    return {"response": response, "audio": audio_response}