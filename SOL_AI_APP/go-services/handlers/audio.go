package handlers
import (
	"fmt"
	"io"
	"net/http"
	"os"
	"github.com/go-audio/wav"

)

func UploadAudio(w http.ResponseWriter, r *http.Request) {
	if r.Method != "POST" { 
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	file, header, err := r.FormFile("audio")
	if err != nil {
		http.Error(w, "Fle upload error", http.StatusBadRequest)
	}
	defer file.Close()

	outFile, err := os.Create("./uploads/" + header.Filename)
	if err != nil {
		http.Error(w, "File save error", http.StatusInternalServerError)
		return
	}
	defer outFile.Close()

	_, err = io.Copy(outFile, file)
	if err != nil {
		http.Error(w, "Failed to save audio", http,StatusInternalServerError)
		return
	}

	// Reopen to Analyze
	audioFile, err := os.Open("./uploaded/" + header.Filename)
	if err != nil {
		http.Error(w, "Failed to read file", http.StatusInternalServerError)
		return
	}
	defer audioFile.Close()

	decoder := wav.NewDecoder(audioFile)
	if !decoder.IsValidFile() {
		http.Error(w, "Invalid WAV file", http.StatusBadRequest)
		return
	}

	fmt.Fprintf(w, "Sample rate: %d Hz, Duration: ~%.2f seconds", 
		decoder.SampleRate, float64(decoder.SampleCount)/float64(decoder.SampleRate))



		