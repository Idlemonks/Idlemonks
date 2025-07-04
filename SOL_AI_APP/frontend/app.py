
import requests
import tempfile
import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, ClientSettings

st.set_page_config("🎙️ ELDA - Voice Input", layout="centered")
st.title("🎤 Talk to ELDA")

st.info("Click start to record audio using your mic.")

webrtc_ctx = webrtc_streamer(
    key="audio",
    mode=WebRtcMode.SENDONLY,
    client_settings=ClientSettings(
        media_stream_constraints={"audio": True, "video": False},
        rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]},
    ),
)

if webrtc_ctx.audio_receiver:
    import av
    import numpy as np

    st.success("Receiving audio...")

    # Collect and process audio frames
    audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
    for audio_frame in audio_frames:
        samples = audio_frame.to_ndarray()
        st.write(f"Audio samples received: {samples.shape}")

