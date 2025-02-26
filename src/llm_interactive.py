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
from rich.markdown import Markdown
from rich import box

from beeminder_api import BeeminderAPI
from scheduler import BeeminderScheduler
from llm_scheduler import LLMScheduler
from ui import console

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
        console.print("0. [white]Return to main menu[/white]")

        choice = prompt("\nEnter your choice (0-3): ",
                      completer=WordCompleter(['0', '1', '2', '3']))

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

    # Check if the API key is set up
    api_key = llm_scheduler.config.get('api_key', '')
    if not api_key:
        console.print("[yellow]API key not set up yet.[/yellow]")
        api_key = llm_scheduler.setup_api_key()
        if not api_key:
            prompt("\nPress Enter to continue... ")
            return

    # Get requirements from the Beeminder scheduler
    console.print("[dim]Fetching current Beeminder requirements...[/dim]")
    requirements = llm_scheduler.beeminder_scheduler.calculate_requirements(days_ahead=7)

    if not requirements:
        console.print("[bold yellow]No scheduled goals found.[/bold yellow]")
        console.print("[dim]Add goals for scheduling first before generating a schedule.[/dim]")
        prompt("\nPress Enter to continue... ")
        return

    console.print(Panel(f"[bold]Found {len(requirements)} goals to schedule[/bold]", border_style="green"))

    # Get start time (empty means round up to nearest 15 minutes)
    time_completer = WordCompleter(['9:00', '9:00 AM', '8:30', '8:00', '7:30', '7:00'])
    now = datetime.now()
    # Round up to nearest 15 minutes
    minutes = now.minute
    rounded_minutes = ((minutes + 14) // 15) * 15  # Round up to next 15-min increment
    if rounded_minutes >= 60:
        rounded_time = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)
    else:
        rounded_time = now.replace(minute=rounded_minutes, second=0, microsecond=0)
    default_start_time = rounded_time.strftime("%I:%M %p").lstrip('0')  # e.g., "3:00 PM"

    while True:
        start_time = prompt(f"Start time for today's schedule (empty for {default_start_time}): ", completer=time_completer)
        if not start_time:  # If empty, use rounded time
            start_time = default_start_time
            break
        if validate_time_format(start_time):
            break
        console.print("[yellow]Invalid time format. Try something like '9:00 AM' or '9:00'.[/yellow]")

    # Get end time (optional)
    end_time_completer = WordCompleter(['5:00 PM', '6:00 PM', '7:00 PM', '8:00 PM', '9:00 PM'])

    while True:
        end_time = prompt("End time (optional, press Enter to skip): ", completer=end_time_completer)
        if not end_time or validate_time_format(end_time):
            break
        console.print("[yellow]Invalid time format. Try something like '5:00 PM' or '17:00'.[/yellow]")

    # Get user preferences or context (optional)
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

    # Generate the schedule
    console.print("\n[bold]Generating your schedule...[/bold]")
    schedule = llm_scheduler.generate_schedule(
        requirements,
        start_time,
        end_time if end_time else None,
        user_preferences
    )

    # Display the schedule
    console.print(Panel(
        Markdown(schedule),
        title="Your Daily Schedule",
        border_style="green",
        box=box.ROUNDED
    ))

    # Option to refine the schedule
    while True:
        console.print("\n[bold]Would you like to refine this schedule?[/bold]")
        refine_choice = prompt("Enter 'yes' to refine or 'no' to finish: ",
                             completer=WordCompleter(['yes', 'no']))

        if refine_choice.lower() != 'yes':
            break

        # Get refinement feedback
        console.print("\n[dim]What would you like to change about this schedule?[/dim]")
        console.print("[dim]Examples: 'Move lunch to 1PM', 'Add more time for coding'[/dim]")

        feedback = []
        while True:
            line = prompt("> ")
            if not line and (not feedback or not feedback[-1]):
                break
            feedback.append(line)

        feedback_text = "\n".join(feedback)

        # Generate refined schedule
        console.print("\n[bold]Refining your schedule...[/bold]")
        schedule = llm_scheduler.refine_schedule(schedule, feedback_text)

        # Display the refined schedule
        console.print(Panel(
            Markdown(schedule),
            title="Your Refined Schedule",
            border_style="green",
            box=box.ROUNDED
        ))

    console.print("\n[dim]Schedule generation complete.[/dim]")
    prompt("\nPress Enter to continue... ")
