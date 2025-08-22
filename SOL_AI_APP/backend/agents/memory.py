history = []

def store_memory(user_input, response):
    history.append((user_input, response))

def retrieve_memory():
    return history [-5:]  # Return the last 5 interactions for context

# WHAT MORE DO I NEED TO ADD IN HISTORY?.
# WHAT WITHIN SOL OR THE USER NEEDS TO BE REMEMBERED

def date_after_days(days: int) -> str:
    """ Helper function to get date after a certain number of days."""
    return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
