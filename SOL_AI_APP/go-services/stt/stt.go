package stt 

type STT interface {
	Transcribe(audio []byte) (string, error)
}
