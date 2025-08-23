# utils.py
from datetime import datetime, timedelta

def is_valid_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def format_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")

def format_time(dt: datetime) -> str:
    return dt.strftime("%H:%M")