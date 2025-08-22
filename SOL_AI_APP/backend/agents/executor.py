def execute(intent, text, memory):
    if intent == "greeting":
        return "Hello! How can I assist you today?"
    elif intent == "reminder":
        return "Reminder has been set."
    elif intent == "task":
        return f"Working on your task: {text}"
    elif intent == "goal":
        return f"Goal set: {text}"
    return "I did not understand that."


# def run_agents(user_input, context=None, priority="normal"):

def date_after_days(days: int) -> str:
    """ Helper function to get date after a certain number of days."""
    return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
