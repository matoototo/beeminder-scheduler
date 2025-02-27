"""
Google Calendar Integration
Functions to create events in Google Calendar from scheduled Beeminder goals
"""

import os
import json
import datetime
import re
from typing import Dict, List, Optional, Tuple
import webbrowser

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from rich.console import Console

console = Console()

# If modifying these scopes, delete your token.json file.
SCOPES = ['https://www.googleapis.com/auth/calendar', 'https://www.googleapis.com/auth/calendar.events']
CLIENT_SECRETS_FILE = os.path.expanduser("~/.beeminder-gcal-credentials.json")
TOKEN_FILE = os.path.expanduser("~/.beeminder-gcal-token.json")

class GoogleCalendarAPI:
    """Interface to Google Calendar API"""

    def __init__(self):
        """Initialize the Google Calendar API client"""
        self.service = None
        self.calendars = None

    def authenticate(self) -> bool:
        """Authenticate with Google Calendar API"""
        creds = None

        # The file token.json stores the user's access and refresh tokens
        if os.path.exists(TOKEN_FILE):
            try:
                creds = Credentials.from_authorized_user_info(
                    json.load(open(TOKEN_FILE)), SCOPES)
            except Exception as e:
                console.print(f"[yellow]Error loading saved credentials: {e}[/yellow]")

        # If there are no valid credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    if not os.path.exists(CLIENT_SECRETS_FILE):
                        console.print("[bold red]❌ Client secrets file not found.[/bold red]")
                        console.print(f"Please create {CLIENT_SECRETS_FILE} with your Google Calendar API credentials.")
                        return False

                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            CLIENT_SECRETS_FILE, SCOPES)
                        creds = flow.run_local_server(port=0)
                    except Exception as e:
                        console.print(f"[bold red]❌ Authentication failed: {e}[/bold red]")
                        return False
            else:
                if not os.path.exists(CLIENT_SECRETS_FILE):
                    console.print("[bold red]❌ Client secrets file not found.[/bold red]")
                    console.print(f"Please create {CLIENT_SECRETS_FILE} with your Google Calendar API credentials.")
                    return False

                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CLIENT_SECRETS_FILE, SCOPES)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    console.print(f"[bold red]❌ Authentication failed: {e}[/bold red]")
                    return False

            # Save the credentials for the next run
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())

        try:
            self.service = build('calendar', 'v3', credentials=creds)
            return True
        except Exception as e:
            console.print(f"[bold red]❌ Failed to create Google Calendar service: {e}[/bold red]")
            return False

    def get_calendar_list(self) -> List[Dict]:
        """Get list of available calendars"""
        if not self.service:
            if not self.authenticate():
                return []

        try:
            calendar_list = self.service.calendarList().list().execute()
            self.calendars = calendar_list.get('items', [])
            return self.calendars
        except Exception as e:
            console.print(f"[bold red]❌ Failed to fetch calendars: {e}[/bold red]")
            return []

    def create_event(self, calendar_id: str, summary: str, start_time: str,
                    end_time: str, description: str = "", color_id: str = None) -> Optional[Dict]:
        """Create a calendar event"""
        if not self.service:
            if not self.authenticate():
                return None

        # Parse times from string format (e.g. "9:00 AM")
        try:
            start_dt = parse_time_string(start_time)
            end_dt = parse_time_string(end_time)

            # Handle end time being on the next day
            if end_dt < start_dt:
                end_dt = end_dt + datetime.timedelta(days=1)

            import time
            local_timezone = time.tzname[0]

            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': local_timezone,
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': local_timezone,
                },
            }

            if color_id:
                event['colorId'] = color_id

            event = self.service.events().insert(calendarId=calendar_id, body=event).execute()
            return event
        except Exception as e:
            console.print(f"[bold red]❌ Failed to create event: {e}[/bold red]")
            return None

    def push_schedule_to_calendar(self, schedule_text: str, calendar_id: str) -> Tuple[int, List[str]]:
        """Parse a schedule and create events in Google Calendar"""
        if not self.service:
            if not self.authenticate():
                return 0, ["Failed to authenticate with Google Calendar"]

        # Regular expression to match schedule lines
        time_pattern = r'(\d{1,2}:\d{2} [AP]M) - (\d{1,2}:\d{2} [AP]M): (.*?)(\((.*?)\))?$'

        events_created = 0
        errors = []

        # Use today's date
        today = datetime.datetime.now().date()

        for line in schedule_text.split('\n'):
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('```'):
                continue

            # Handle markdown list items format from LLM output
            if line.startswith('- '):
                line = line[2:].strip()

            match = re.search(time_pattern, line)
            if match:
                start_time_str, end_time_str, activity, _, goal_name = match.groups()

                # Create summary from activity and goal
                if goal_name:
                    summary = f"{activity} ({goal_name})"
                else:
                    summary = activity

                # Create event
                description = f"Beeminder Schedule\nActivity: {activity}"
                if goal_name:
                    description += f"\nGoal: {goal_name}"

                # Determine color based on activity type
                color_id = None
                activity_lower = activity.lower()
                if 'break' in activity_lower or 'lunch' in activity_lower:
                    color_id = '7'  # Default calendar green
                elif goal_name:
                    # Use different colors for different goals
                    # This is a simple hash function to assign consistent colors
                    goal_hash = sum(ord(c) for c in goal_name) % 11 + 1
                    color_id = str(goal_hash)

                try:
                    event = self.create_event(
                        calendar_id=calendar_id,
                        summary=summary,
                        start_time=start_time_str,
                        end_time=end_time_str,
                        description=description,
                        color_id=color_id
                    )

                    if event:
                        events_created += 1
                    else:
                        errors.append(f"Failed to create event: {summary}")
                except Exception as e:
                    errors.append(f"Error creating event {summary}: {str(e)}")

        return events_created, errors


def setup_google_calendar() -> bool:
    """Guide the user through setting up Google Calendar API"""

    console.print("\n[bold cyan]Google Calendar Setup[/bold cyan]")
    console.print("""
To use Google Calendar integration, you need to create OAuth credentials:
1. Go to https://console.cloud.google.com/
2. Create a new project (or select an existing one)
3. Navigate to "APIs & Services" > "Credentials"
4. Click "Create Credentials" > "OAuth client ID"
5. Set application type to "Desktop app"
6. Download the JSON file and save it as:
   [bold]~/.beeminder-gcal-credentials.json[/bold]
""")

    choice = input("Do you want to open the Google Cloud Console now? (y/n): ")
    if choice.lower() == 'y':
        webbrowser.open("https://console.cloud.google.com/apis/credentials")

    if os.path.exists(CLIENT_SECRETS_FILE):
        console.print("[green]✓ Credentials file found![/green]")

        # Test authentication
        api = GoogleCalendarAPI()
        if api.authenticate():
            console.print("[bold green]✓ Successfully authenticated with Google Calendar![/bold green]")
            return True
        else:
            console.print("[yellow]⚠ Authentication failed. Please check your credentials file.[/yellow]")
            return False
    else:
        console.print(f"[yellow]⚠ Credentials file not found at {CLIENT_SECRETS_FILE}[/yellow]")
        console.print("Please download your credentials JSON file and place it at the path above.")
        return False


def parse_time_string(time_str: str) -> datetime.datetime:
    """Parse time string like '9:00 AM' to a datetime object"""
    today = datetime.datetime.now().date()

    # Try different formats
    formats = [
        "%I:%M %p",  # "9:00 AM"
        "%I:%M%p",   # "9:00AM"
        "%I %p",     # "9 AM"
    ]

    for fmt in formats:
        try:
            time_part = datetime.datetime.strptime(time_str.strip(), fmt)
            return datetime.datetime.combine(today, time_part.time())
        except ValueError:
            continue

    # If all formats fail, raise exception
    raise ValueError(f"Could not parse time string: {time_str}")
