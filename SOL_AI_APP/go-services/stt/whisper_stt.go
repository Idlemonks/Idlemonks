package stt


import "fmt"

type WhisperSTT struct{}

func NewWhisperSTT() *WhisperSTT{
	return &WhisperSTT{}
}

func (w *WhisperSTT) Transcribe(audio []byte) (string, error) {
	fmt.Println("Whisper STT received audio of length:", len(audio))
	return "Transcribed text from Whisper STT", nil
}