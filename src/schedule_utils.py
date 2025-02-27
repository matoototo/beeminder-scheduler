"""
Utility functions for schedule management
Shared between interactive and LLM modules
"""

import os

# Path to store the last generated schedule
LAST_SCHEDULE_FILE = os.path.expanduser("~/.beeminder-last-schedule.txt")

def save_last_schedule(schedule_text: str) -> None:
    """Save the last generated schedule to a file"""
    with open(LAST_SCHEDULE_FILE, 'w') as f:
        f.write(schedule_text)

def get_last_schedule() -> str:
    """Get the last generated schedule from a file"""
    if os.path.exists(LAST_SCHEDULE_FILE):
        with open(LAST_SCHEDULE_FILE, 'r') as f:
            return f.read()
    return ""
