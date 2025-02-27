"""
Interactive mode for LLM Scheduler
Implements the LLM scheduling functionality and menu system
"""

import os
import re
from datetime import datetime
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from rich.panel import Panel

from beeminder_api import BeeminderAPI
from scheduler import BeeminderScheduler
from llm_scheduler import LLMScheduler
from ui import console, display_schedule
from google_calendar import GoogleCalendarAPI
from schedule_utils import save_last_schedule

def start_llm_interactive_mode(api: BeeminderAPI, scheduler: BeeminderScheduler) -> None:
    try:
        llm_scheduler = LLMScheduler(api, scheduler)
        show_llm_menu(llm_scheduler)
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting LLM scheduler...[/yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")

def show_llm_menu(llm_scheduler: LLMScheduler) -> None:
    while True:
        console.clear()

        console.print(Panel(
            "[bold cyan]Beeminder LLM Scheduler[/bold cyan]\n"
            "[dim]Generate daily schedules based on your Beeminder goals[/dim]",
            border_style="blue"
        ))

        console.print("\n[bold]What would you like to do?[/bold]")
        console.print("1. [green]Generate daily schedule[/green]")
        console.print("2. [blue]Setup API key[/blue]")
        console.print("3. [yellow]Edit prompt template[/yellow]")
        console.print("4. [cyan]Generate schedule and push to Google Calendar[/cyan]")
        console.print("0. [white]Return to main menu[/white]")

        choice = prompt("\nEnter your choice (0-4): ",
                      completer=WordCompleter(['0', '1', '2', '3', '4']))

        if choice == "0":
            break
        elif choice == "1":
            generate_daily_schedule(llm_scheduler)
        elif choice == "2":
            llm_scheduler.setup_api_key()
            prompt("\nPress Enter to continue... ")
        elif choice == "3":
            llm_scheduler.edit_prompt_template()
            prompt("\nPress Enter to continue... ")
        elif choice == "4":
            generate_and_push_to_calendar(llm_scheduler)
        else:
            console.print("[bold red]Invalid choice![/bold red]")
            prompt("\nPress Enter to continue... ")

def validate_time_format(time_str: str) -> bool:
    if not time_str:
        return True  # Empty string is valid for end time

    patterns = [
        r'^\d{1,2}:\d{2}$',             # 9:00 or 14:30
        r'^\d{1,2}:\d{2}\s*[ap]m$',     # 9:00am or 2:30 pm
        r'^\d{1,2}\s*[ap]m$',           # 9am or 2 pm
        r'^\d{1,2}$'                    # Just the hour: 9 or 14
    ]

    time_str = time_str.lower().strip()
    for pattern in patterns:
        if re.match(pattern, time_str):
            return True

    return False

def generate_daily_schedule(llm_scheduler: LLMScheduler) -> None:
    console.clear()
    console.print("[bold cyan]Generate Daily Schedule[/bold cyan]")

    api_key = llm_scheduler.config.get('api_key', '')
    if not api_key:
        console.print("[yellow]API key not set up yet.[/yellow]")
        api_key = llm_scheduler.setup_api_key()
        if not api_key:
            prompt("\nPress Enter to continue... ")
            return

    console.print("[dim]Fetching today's Beeminder requirements...[/dim]")
    requirements = llm_scheduler.beeminder_scheduler.calculate_requirements()

    if not requirements:
        console.print("[bold yellow]No scheduled goals found.[/bold yellow]")
        console.print("[dim]Add goals for scheduling first before generating a schedule.[/dim]")
        prompt("\nPress Enter to continue... ")
        return

    console.print(Panel(f"[bold]Found {len(requirements)} goals to schedule[/bold]", border_style="green"))

    time_completer = WordCompleter(['9:00', '9:00 AM', '8:30', '8:00', '7:30', '7:00'])
    now = datetime.now()
    minutes = now.minute
    rounded_minutes = ((minutes + 14) // 15) * 15
    if rounded_minutes >= 60:
        rounded_time = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)
    else:
        rounded_time = now.replace(minute=rounded_minutes, second=0, microsecond=0)
    default_start_time = rounded_time.strftime("%I:%M %p").lstrip('0')

    while True:
        start_time = prompt(f"Start time for today's schedule (empty for {default_start_time}): ", completer=time_completer)
        if not start_time:
            start_time = default_start_time
            break
        if validate_time_format(start_time):
            break
        console.print("[yellow]Invalid time format. Try something like '9:00 AM' or '9:00'.[/yellow]")

    end_time_completer = WordCompleter(['5:00 PM', '6:00 PM', '7:00 PM', '8:00 PM', '9:00 PM'])
    while True:
        end_time = prompt("End time (optional, press Enter to skip): ", completer=end_time_completer)
        if not end_time or validate_time_format(end_time):
            break
        console.print("[yellow]Invalid time format. Try something like '5:00 PM' or '17:00'.[/yellow]")

    console.print("\n[dim]Enter any preferences or context for your schedule.[/dim]")
    console.print("[dim]Examples: 'I need a lunch break around noon', 'I have a meeting at 2PM'[/dim]")
    console.print("[dim]Press Enter twice on an empty line when done.[/dim]")

    preferences = []
    while True:
        line = prompt("> ", history=FileHistory(os.path.expanduser("~/.beeminder-preferences-history")))
        if not line and (not preferences or not preferences[-1]):
            break
        preferences.append(line)

    user_preferences = "\n".join(preferences)

    console.print("\n[bold]Generating your schedule...[/bold]")
    schedule = llm_scheduler.generate_schedule(
        requirements,
        start_time,
        end_time if end_time else None,
        user_preferences
    )

    # Save the generated schedule for later use
    save_last_schedule(schedule)

    display_schedule(schedule)

    while True:
        console.print("\n[bold]Would you like to refine this schedule?[/bold]")
        refine_choice = prompt("Enter 'yes' to refine or 'no' to finish: ",
                             completer=WordCompleter(['yes', 'no']))
        if refine_choice.lower() != 'yes':
            break

        console.print("\n[dim]What would you like to change about this schedule?[/dim]")
        console.print("[dim]Examples: 'Move lunch to 1PM', 'Add more time for coding'[/dim]")

        feedback = []
        while True:
            line = prompt("> ")
            if not line and (not feedback or not feedback[-1]):
                break
            feedback.append(line)

        feedback_text = "\n".join(feedback)

        console.print("\n[bold]Refining your schedule...[/bold]")
        schedule = llm_scheduler.refine_schedule(schedule, feedback_text)

        # Save the refined schedule
        save_last_schedule(schedule)

        display_schedule(schedule)

    console.print("\n[dim]Schedule generation complete.[/dim]")
    prompt("\nPress Enter to continue... ")

def generate_and_push_to_calendar(llm_scheduler: LLMScheduler) -> None:
    """Generate a schedule and push it to Google Calendar"""
    console.clear()
    console.print("[bold cyan]Generate Schedule and Push to Google Calendar[/bold cyan]")

    # First, generate a schedule
    api_key = llm_scheduler.config.get('api_key', '')
    if not api_key:
        console.print("[yellow]API key not set up yet.[/yellow]")
        api_key = llm_scheduler.setup_api_key()
        if not api_key:
            prompt("\nPress Enter to continue... ")
            return

    console.print("[dim]Fetching today's Beeminder requirements...[/dim]")
    requirements = llm_scheduler.beeminder_scheduler.calculate_requirements()

    if not requirements:
        console.print("[bold yellow]No scheduled goals found.[/bold yellow]")
        console.print("[dim]Add goals for scheduling first before generating a schedule.[/dim]")
        prompt("\nPress Enter to continue... ")
        return

    console.print(Panel(f"[bold]Found {len(requirements)} goals to schedule[/bold]", border_style="green"))

    # Get start time
    time_completer = WordCompleter(['9:00', '9:00 AM', '8:30', '8:00', '7:30', '7:00'])
    now = datetime.now()
    minutes = now.minute
    rounded_minutes = ((minutes + 14) // 15) * 15
    if rounded_minutes >= 60:
        rounded_time = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)
    else:
        rounded_time = now.replace(minute=rounded_minutes, second=0, microsecond=0)
    default_start_time = rounded_time.strftime("%I:%M %p").lstrip('0')

    while True:
        start_time = prompt(f"Start time for today's schedule (empty for {default_start_time}): ", completer=time_completer)
        if not start_time:
            start_time = default_start_time
            break
        if validate_time_format(start_time):
            break
        console.print("[yellow]Invalid time format. Try something like '9:00 AM' or '9:00'.[/yellow]")

    end_time_completer = WordCompleter(['5:00 PM', '6:00 PM', '7:00 PM', '8:00 PM', '9:00 PM'])
    while True:
        end_time = prompt("End time (optional, press Enter to skip): ", completer=end_time_completer)
        if not end_time or validate_time_format(end_time):
            break
        console.print("[yellow]Invalid time format. Try something like '5:00 PM' or '17:00'.[/yellow]")

    console.print("\n[dim]Enter any preferences or context for your schedule.[/dim]")
    console.print("[dim]Examples: 'I need a lunch break around noon', 'I have a meeting at 2PM'[/dim]")
    console.print("[dim]Press Enter twice on an empty line when done.[/dim]")

    preferences = []
    while True:
        line = prompt("> ", history=FileHistory(os.path.expanduser("~/.beeminder-preferences-history")))
        if not line and (not preferences or not preferences[-1]):
            break
        preferences.append(line)

    user_preferences = "\n".join(preferences)

    console.print("\n[bold]Generating your schedule...[/bold]")
    schedule = llm_scheduler.generate_schedule(
        requirements,
        start_time,
        end_time if end_time else None,
        user_preferences
    )

    # Save the generated schedule for later use
    save_last_schedule(schedule)

    display_schedule(schedule)

    # Authenticate with Google Calendar and get default calendar
    console.print("\n[bold]Preparing to push to Google Calendar...[/bold]")

    # Get calendar ID from config
    config_file = os.path.expanduser("~/.beeminder-schedule.json")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {}

    calendar_id = config.get('google_calendar_id', '')

    # If no default calendar set, get calendar list and select one
    gcal_api = GoogleCalendarAPI()
    if not gcal_api.authenticate():
        console.print("[bold red]❌ Failed to authenticate with Google Calendar[/bold red]")
        console.print("[dim]Run 'gcal setup' first to configure Google Calendar access[/dim]")
        prompt("\nPress Enter to continue... ")
        return

    if not calendar_id:
        calendars = gcal_api.get_calendar_list()

        if not calendars:
            console.print("[yellow]No calendars found[/yellow]")
            prompt("\nPress Enter to continue... ")
            return

        # Show calendars and let user select one
        from rich.table import Table
        from rich import box

        table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", width=4)
        table.add_column("Calendar ID", style="dim")
        table.add_column("Name", style="bold")

        for i, calendar in enumerate(calendars, 1):
            table.add_row(
                str(i),
                calendar.get('id', ''),
                calendar.get('summary', '')
            )

        console.print(table)

        calendar_choice = prompt("\nSelect calendar # to use: ",
                               completer=WordCompleter([str(i) for i in range(1, len(calendars) + 1)]))

        if not calendar_choice.isdigit():
            console.print("[yellow]Invalid selection, operation cancelled.[/yellow]")
            prompt("\nPress Enter to continue... ")
            return

        calendar_index = int(calendar_choice) - 1
        if calendar_index < 0 or calendar_index >= len(calendars):
            console.print("[bold red]Invalid selection![/bold red]")
            prompt("\nPress Enter to continue... ")
            return

        calendar_id = calendars[calendar_index].get('id', '')

        # Ask if they want to save this as default
        save_default = prompt("Save this as your default calendar? (yes/no): ",
                            completer=WordCompleter(['yes', 'no']))

        if save_default.lower() == 'yes':
            config['google_calendar_id'] = calendar_id
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            console.print("[green]✓ Saved as default calendar[/green]")

    # Confirm with user
    calendar_name = "selected calendar"
    for cal in gcal_api.get_calendar_list():
        if cal.get('id') == calendar_id:
            calendar_name = cal.get('summary', 'selected calendar')
            break

    console.print(f"\n[bold]Ready to push schedule to calendar:[/bold] [cyan]{calendar_name}[/cyan]")
    confirm = prompt("Confirm push to Google Calendar? (yes/no): ",
                   completer=WordCompleter(['yes', 'no']))

    if confirm.lower() != 'yes':
        console.print("[yellow]Operation cancelled.[/yellow]")
        prompt("\nPress Enter to continue... ")
        return

    # Push to Google Calendar
    console.print("\n[bold]Pushing schedule to Google Calendar...[/bold]")
    events_created, errors = gcal_api.push_schedule_to_calendar(schedule, calendar_id)

    if events_created > 0:
        console.print(f"[bold green]✓ Successfully created {events_created} calendar events![/bold green]")

    if errors:
        console.print("[yellow]The following errors occurred:[/yellow]")
        for error in errors:
            console.print(f"- {error}")

    prompt("\nPress Enter to continue... ")
