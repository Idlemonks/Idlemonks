def date_after_days(days: int) -> str:
    """ Helper function to get date after a certain number of days."""
    return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
