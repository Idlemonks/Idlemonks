history = []

def store_memory(user_input, response):
    history.append((user_input, response))

def retrieve_memory():
    return history [-5:]  # Return the last 5 interactions for context

# WHAT MORE DO I NEED TO ADD IN HISTORY?.
# WHAT WITHIN SOL OR THE USER NEEDS TO BE REMEMBERED