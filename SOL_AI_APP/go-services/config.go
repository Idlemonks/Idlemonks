package main

import (
	"os"

)

type Config struct {
	TTSProvider string
	STTProvider string 
	GoogleTTSAPIKey string
	WhisperSTTModelPath string
}

func LoadConfig() Config{
	return Config{
		TTSProvider: os.Getenv("TTSProvider"), // e.g., "google"
		STTProvider: os.Getenv("STTProvider"), // e.g., "whisper"
	}
}