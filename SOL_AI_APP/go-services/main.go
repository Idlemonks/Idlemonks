package main 

import (
	"fmt"
	"net/http"
	"log"
	"os"
	"sol-go/stt"
	"sol-go/tts"
)
// Global variables for TTS and STT engines 
var ttsEngine tts.TTS 
var sttEngine stt.STT


func main() {
	// LOAD CONFIG FROM ENVIROMENT VARIABLES
	os.Setenv("TTS_PROVIDER", "google")
	os.Setenv("STT_PROVIDER", "whisper")
	cfg := LoadConfig()

	// Initialize TTS ENGINE
	switch cfg.TTSProvider {
	case "google":
		ttsEngine = tts.NewGoogleTTS()
	default:
		log.Fatalf("Unsupported TTS provider: %s", cfg.TTSProvider)
	}

	// Initialize STT ENGINE
	switch cfg.STTProvider {
	case "whisper":
		sttEngine = stt.NewWhisperSTT()
	default:
		log.Fatalf("Unsupported STT provider: %s", cfg.STTProvider)
	}

	// Set up HTTP handlers
	http.HandleFunc("/upload_audio", UploadAudio)
	log.Println("Go audio service listening on port 8081...")
	log.Fatal(http.ListenAndServe(":8081", nil))
}

// HTTP handler function for /upload_audio
func UploadAudio(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Read audio from multipart form field "audio"
	file, _, err := r.FormFile("audio")
	if err != nil {
		http.Error(w, "Failed to read audio file: "+err.Error(), http.StatusBadRequest)
		return
	}
	defer file.Close()

	audioData := make([]byte, r.ContentLength)
	_, err = file.Read(audioData)
	if err != nil {
		http.Error(w, "failed to read audio content: "+err.Error(), http.StatusBadRequest)
		return
	}

	// Transcribe using STT engine
	transcribedText, err := sttEngine.Transcribe(audioData)
	if err != nil {
		http.Error(w, "Transcription failed: "+err.Error(), http.StatusInternalServerError)
		return
	}

	// Respond with transcribed text
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{"transcription": "%s"}`, transcribedText)
}

