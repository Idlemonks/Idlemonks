from transformers import pipeline

classifier = pipeline("zero-shot-classification")

def extract_intent(text):
    labels = ["weather", "reminder", "greeting", "task"]
    result = classifier(text, labels)
    return result['labels'] [0]  # Return the highest scoring label as

def date_after_days(days: int) -> str:
    """ Helper function to get date after a certain number of days."""
    return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
