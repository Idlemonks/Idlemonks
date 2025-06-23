package main

import (
	"os"

)

type Config struct {
	TTSProvider string
	STTProvider string 
}

func LoadConfig() Config{
	return Config{
		TTSProvider: os.Getenv("TTS_PROVIDER"), // e.g., "google"
		STTProvider: os.Getenv("STT_PROVIDER"), '' e.g., "whisper"
	}
}