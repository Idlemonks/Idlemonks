package tts 

type TTS interface {
	Speak(text string) ([]byte, error)
}