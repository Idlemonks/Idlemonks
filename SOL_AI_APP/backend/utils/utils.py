import os
from datetime import datetime
import shutil
import logging

# Setup basic logging
logging.basicConfig(
    filename = 'audio_saver.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'

)

def save_audio(file, upload_dir="audio_uploads/"):
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"{datetime.now().isoformat().replace(':','_')}.wav"
    path = os.path.join(upload_dir, filename)

    try:

        with open(path, "wb") as f:
            shutil.copyfileobj(file, f)
        logging.info(f"Audio file saved: {path}")
    except Exception as e:
        logging.error(f"Failed to save audio file: {e}")
        raise

    return path
