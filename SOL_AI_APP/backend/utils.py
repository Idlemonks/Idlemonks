import os
from datetime import datetime
import shutil

def save_audio(file, upload_dir="audio_uploads/"):
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{datetime.now().isoformat().replace(':','_')}.wav"
    path = os.path.join(upload_dir, filename)
    with open(path, "wb") as f:
        shutil.copyfileobj(file, f)
    return path
