import streamlit as st
import requests
import tempfile

st.set_page_config("🎤 ELDA", layout="centered")
st.title("🎙️ Talk to ELDA")

audio_bytes = st.audio_recorder("🎤 Record Your Voice", format="wav")

if audio_bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_bytes)
        f_path = f.name

    st.info("⌛ Sending to agent...")

    with open(f_path, "rb") as audio_file:
        response = requests.post(
            "http://localhost:8000/process_audio/",
            files={"file": audio_file}
        )

    st.audio(response.content)
