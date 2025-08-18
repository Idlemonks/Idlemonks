from transformers import pipeline

classifier = pipeline("zero-shot-classification")

def extract_intent(text):
    labels = ["weather", "reminder", "greeting", "task"]
    result = classifier(text, labels)
    return result['labels'] [0]  # Return the highest scoring label as