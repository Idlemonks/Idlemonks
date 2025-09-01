from fastapi import FastAPI, WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    #forward to STT service or queue
    await websocket.accept()
    await websocket.send_text("Audio Received")