"""
Interactive mode for Beeminder Scheduler
Implements the interactive menu system
"""

import os
import json
from datetime import datetime
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from rich.panel import Panel
from rich.table import Table
from rich import box

from beeminder_api import BeeminderAPI
from scheduler import BeeminderScheduler
from schedule_utils import get_last_schedule, LAST_SCHEDULE_FILE
from ui import console
from llm_interactive import start_llm_interactive_mode
from google_calendar import GoogleCalendarAPI, setup_google_calendar

def start_interactive_mode(api: BeeminderAPI, scheduler: BeeminderScheduler) -> None:
    try:
        console.print(Panel(
            f"Configuration file:\n[bold cyan]{scheduler.config_file}[/bold cyan]",
            title="Config Location",
            border_style="dim"
        ))
        show_interactive_menu(api, scheduler)
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting interactive mode...[/yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")

def show_interactive_menu(api: BeeminderAPI, scheduler: BeeminderScheduler) -> None:
    while True:
        console.clear()

        # Create header with config info
        header_text = (
            "[bold cyan]Beeminder Scheduler[/bold cyan]\n"
            "[dim]Integrate your Beeminder goals with your calendar[/dim]\n\n"
            f"[dim]Config: [bold]{scheduler.config_file}[/bold] "
        )
        console.print(Panel(header_text, border_style="blue"))

        # Show scheduled goals summary
        scheduled_goals = scheduler.get_scheduled_goals()
        if scheduled_goals:
            table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
            table.add_column("Goal", style="dim")
            table.add_column("Calendar Name", style="cyan")
            table.add_column("Hours Per Unit", justify="right")

            for slug, goal in scheduled_goals.items():
                table.add_row(
                    slug,
                    goal.calendar_name,
                    str(goal.hours_per_unit)
                )

            console.print(Panel(table, title="Scheduled Goals", border_style="blue"))
        else:
            console.print(Panel(
                "[italic]No goals configured for scheduling yet.[/italic]",
                title="Scheduled Goals",
                border_style="yellow"
            ))

        # Show menu options
        console.print("\n[bold]What would you like to do?[/bold]")
        console.print("1. [green]View all Beeminder goals[/green]")
        console.print("2. [blue]Add goal to scheduling[/blue]")
        console.print("3. [red]Remove goal from scheduling[/red]")
        console.print("4. [yellow]Edit goal settings[/yellow]")
        console.print("5. [magenta]Show scheduling requirements[/magenta]")
        console.print("6. [cyan]LLM Schedule Generator[/cyan]")
        console.print("7. [green]Google Calendar Integration[/green]")
        console.print("0. [white]Exit[/white]")

        choice = prompt("\nEnter your choice (0-7): ",
                      completer=WordCompleter(['0', '1', '2', '3', '4', '5', '6', '7']))

        if choice == "0":
            break
        elif choice == "1":
            view_all_goals(api, scheduler)
        elif choice == "2":
            add_goal_to_scheduling(api, scheduler)
        elif choice == "3":
            remove_goal_from_scheduling(scheduler)
        elif choice == "4":
            edit_goal_settings(api, scheduler)
        elif choice == "5":
            show_scheduling_requirements(scheduler)
        elif choice == "6":
            start_llm_interactive_mode(api, scheduler)
        elif choice == "7":
            show_google_calendar_menu(api, scheduler)
        else:
            console.print("[bold red]Invalid choice![/bold red]")
            prompt("\nPress Enter to continue... ")

def show_google_calendar_menu(api: BeeminderAPI, scheduler: BeeminderScheduler) -> None:
    """Show the Google Calendar integration menu"""
    while True:
        console.clear()
        console.print("[bold cyan]Google Calendar Integration[/bold cyan]")

        # Check if we have a last generated schedule
        has_schedule = os.path.exists(LAST_SCHEDULE_FILE)

        console.print("\n[bold]What would you like to do?[/bold]")
        console.print("1. [blue]Setup Google Calendar integration[/blue]")
        console.print("2. [green]List available calendars[/green]")
        if has_schedule:
            console.print("3. [cyan]Push current schedule to Google Calendar[/cyan]")
        console.print("0. [white]Return to main menu[/white]")

        max_choice = "3" if has_schedule else "2"
        choice = prompt(f"\nEnter your choice (0-{max_choice}): ",
                      completer=WordCompleter(['0', '1', '2'] + (['3'] if has_schedule else [])))

        if choice == "0":
            break
        elif choice == "1":
            setup_google_calendar()
            prompt("\nPress Enter to continue... ")
        elif choice == "2":
            list_google_calendars(scheduler)
        elif choice == "3" and has_schedule:
            push_schedule_to_calendar(scheduler)
        else:
            console.print("[bold red]Invalid choice![/bold red]")
            prompt("\nPress Enter to continue... ")

def list_google_calendars(scheduler: BeeminderScheduler) -> None:
    """List available Google Calendars and set default"""
    console.clear()
    console.print("[bold cyan]Google Calendars[/bold cyan]")

    api = GoogleCalendarAPI()
    if not api.authenticate():
        console.print("[bold red]❌ Failed to authenticate with Google Calendar[/bold red]")
        prompt("\nPress Enter to continue... ")
        return

    calendars = api.get_calendar_list()

    if not calendars:
        console.print("[yellow]No calendars found[/yellow]")
        prompt("\nPress Enter to continue... ")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Calendar ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Default", justify="center")

    # Load config to check for default calendar
    config_file = os.path.expanduser("~/.beeminder-schedule.json")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {}

    default_calendar_id = config.get('google_calendar_id', '')

    for i, calendar in enumerate(calendars, 1):
        calendar_id = calendar.get('id', '')
        is_default = calendar_id == default_calendar_id

        table.add_row(
            str(i),
            calendar_id,
            calendar.get('summary', ''),
            "[bold green]✓[/bold green]" if is_default else ""
        )

    console.print(table)

    # Prompt to set default
    console.print("\n[dim]You can set a default calendar to use for all schedule pushes.[/dim]")
    calendar_choice = prompt("Select calendar # to set as default (or 0 to return): ",
                           completer=WordCompleter([str(i) for i in range(len(calendars) + 1)]))

    if calendar_choice == "0" or not calendar_choice.isdigit():
        return

    calendar_index = int(calendar_choice) - 1
    if calendar_index < 0 or calendar_index >= len(calendars):
        console.print("[bold red]Invalid selection![/bold red]")
        prompt("\nPress Enter to continue... ")
        return

    selected_calendar = calendars[calendar_index]
    selected_id = selected_calendar.get('id', '')
    selected_name = selected_calendar.get('summary', '')

    config['google_calendar_id'] = selected_id
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    console.print(f"[bold green]✓ Set [bold]{selected_name}[/bold] as default calendar![/bold green]")
    prompt("\nPress Enter to continue... ")

def push_schedule_to_calendar(scheduler: BeeminderScheduler) -> None:
    """Push the last generated schedule to Google Calendar"""
    console.clear()
    console.print("[bold cyan]Push Schedule to Google Calendar[/bold cyan]")

    # Get the last generated schedule
    schedule_text = get_last_schedule()
    if not schedule_text:
        console.print("[yellow]No recently generated schedule found[/yellow]")
        console.print("[dim]Generate a schedule first using the LLM Schedule Generator[/dim]")
        prompt("\nPress Enter to continue... ")
        return

    # Check if a default calendar is set
    config_file = os.path.expanduser("~/.beeminder-schedule.json")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {}

    default_calendar_id = config.get('google_calendar_id', '')

    if not default_calendar_id:
        console.print("[yellow]No default calendar is set[/yellow]")
        console.print("[dim]Please select a default calendar first[/dim]")
        list_google_calendars(scheduler)
        return

    # Authenticate with Google Calendar
    api = GoogleCalendarAPI()
    if not api.authenticate():
        console.print("[bold red]❌ Failed to authenticate with Google Calendar[/bold red]")
        prompt("\nPress Enter to continue... ")
        return

    # Confirm with user
    console.print("[dim]Ready to push the current schedule to Google Calendar.[/dim]")
    confirm = prompt("Do you want to continue? (yes/no): ",
                   completer=WordCompleter(['yes', 'no']))

    if confirm.lower() != 'yes':
        console.print("[yellow]Operation cancelled.[/yellow]")
        prompt("\nPress Enter to continue... ")
        return

    # Push schedule to calendar
    console.print("[bold]Pushing schedule to Google Calendar...[/bold]")
    events_created, errors = api.push_schedule_to_calendar(schedule_text, default_calendar_id)

    if events_created > 0:
        console.print(f"[bold green]✓ Successfully created {events_created} calendar events![/bold green]")

    if errors:
        console.print("[yellow]The following errors occurred:[/yellow]")
        for error in errors:
            console.print(f"- {error}")

    prompt("\nPress Enter to continue... ")

def show_scheduling_requirements(scheduler: BeeminderScheduler) -> None:
    console.clear()
    console.print("[bold cyan]Scheduling Requirements[/bold cyan]")

    console.print("[dim]Calculating today's requirements...[/dim]")
    requirements = scheduler.calculate_requirements()

    if not requirements:
        console.print("[bold yellow]No scheduled goals found[/bold yellow]")
        prompt("\nPress Enter to continue... ")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Activity", style="bold")
    table.add_column("Units Needed", justify="right")
    table.add_column("Hours Needed", justify="right")
    table.add_column("Hours/Day", justify="right")
    table.add_column("Buffer", justify="center")
    table.add_column("Deadline", justify="center")
    table.add_column("Beeminder Says", justify="left")

    total_hours = 0
    for slug, data in requirements.items():
        deadline_str = data['deadline'].strftime("%Y-%m-%d")
        row_style = data['urgency']
        buffer_days = data['safebuf']
        buffer_text = f"{buffer_days} days"
        hours = data['hours_needed']
        total_hours += hours

        table.add_row(
            data['calendar_name'],
            f"{data['delta']:.1f}",
            f"{hours:.1f}",
            f"{data['hours_per_day']:.1f}",
            buffer_text,
            deadline_str,
            data.get('limsum', ''),
            style=row_style
        )

    console.print(table)
    console.print(f"\n[bold]Total hours needed today:[/bold] [cyan]{total_hours:.1f}[/cyan]")
    prompt("\nPress Enter to continue... ")

def view_all_goals(api: BeeminderAPI, scheduler: BeeminderScheduler) -> None:
    console.clear()
    console.print("[bold cyan]All Beeminder Goals[/bold cyan]")

    all_goals = api.get_goals()
    scheduled_goals = scheduler.get_scheduled_goals()
    scheduled_slugs = {goal.slug for goal in scheduled_goals.values()}

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Goal ID", style="dim", width=12)
    table.add_column("Title", min_width=20)
    table.add_column("Progress", justify="right")
    table.add_column("Deadline", justify="center")
    table.add_column("Scheduled", justify="center", width=10)

    for i, goal in enumerate(all_goals, 1):
        slug = goal.get('slug')
        deadline = datetime.fromtimestamp(goal.get('losedate', 0))
        days_left = (deadline - datetime.now()).days

        if days_left < 1:
            deadline_str = f"[bold red]{deadline.strftime('%Y-%m-%d')}[/bold red]"
        elif days_left < 3:
            deadline_str = f"[yellow]{deadline.strftime('%Y-%m-%d')}[/yellow]"
        else:
            deadline_str = deadline.strftime("%Y-%m-%d")

        scheduled_str = "[bold green]✓[/bold green]" if slug in scheduled_slugs else ""

        curval = goal.get('curval')
        goalval = goal.get('goalval')
        gunits = goal.get('gunits', '')

        if curval is not None and goalval is not None:
            progress = f"{curval:.1f}/{goalval:.1f} {gunits}"
        elif curval is not None:
            progress = f"{curval:.1f} {gunits}"
        elif goalval is not None:
            progress = f"?/{goalval:.1f} {gunits}"
        else:
            progress = f"? {gunits}"

        table.add_row(
            str(i),
            slug,
            goal.get('title', ''),
            progress,
            deadline_str,
            scheduled_str
        )

    console.print(table)
    prompt("\nPress Enter to continue... ")

def add_goal_to_scheduling(api: BeeminderAPI, scheduler: BeeminderScheduler) -> None:
    console.clear()
    console.print("[bold cyan]Add Goal to Scheduling[/bold cyan]")

    all_goals = api.get_goals()
    scheduled_goals = scheduler.get_scheduled_goals()
    scheduled_slugs = set(scheduled_goals.keys())
    available_goals = [g for g in all_goals if g['slug'] not in scheduled_slugs]

    if not available_goals:
        console.print("[bold yellow]All goals are already scheduled![/bold yellow]")
        prompt("\nPress Enter to continue... ")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Goal ID", style="dim")
    table.add_column("Title")
    table.add_column("Units", justify="center")

    for i, goal in enumerate(available_goals, 1):
        table.add_row(
            str(i),
            goal.get('slug'),
            goal.get('title', ''),
            goal.get('gunits', '')
        )

    console.print(table)
    goal_numbers = [str(i) for i in range(len(available_goals) + 1)]  # Include 0 for return
    goal_choice = prompt("\nSelect goal # to add (or 0 to return to main menu): ",
                       completer=WordCompleter(goal_numbers))

    if goal_choice == "0" or not goal_choice.isdigit():
        return

    goal_index = int(goal_choice) - 1
    if goal_index < 0 or goal_index >= len(available_goals):
        console.print("[bold red]Invalid selection![/bold red]")
        prompt("\nPress Enter to continue... ")
        return

    selected_goal = available_goals[goal_index]
    slug = selected_goal['slug']
    title = selected_goal['title']

    console.print(f"\n[bold]Selected:[/bold] {slug} - {title}")
    console.print("\n[dim]The calendar name is what will appear in your calendar events.[/dim]")

    calendar_name = prompt(f"Calendar event name [{title}]: ",
                         completer=WordCompleter([title]))
    if not calendar_name:
        calendar_name = title

    units = selected_goal.get('gunits', 'units')
    console.print(f"\n[dim]How many hours does each {units} of this goal take?[/dim]")
    console.print(f"[dim]Examples: Reading goal: 0.05 hours per page, Coding: 3 hours per commit[/dim]")

    while True:
        hours_input = prompt(f"Hours per {units} [1.0] (can use fractions like 1/20): ")
        if not hours_input:
            hours_per_unit = 1.0
            break

        try:
            if '/' in hours_input:
                numerator, denominator = hours_input.split('/', 1)
                try:
                    hours_per_unit = float(numerator.strip()) / float(denominator.strip())
                except (ValueError, ZeroDivisionError):
                    console.print("[bold red]Invalid fraction format. Use format like '1/20'[/bold red]")
                    continue
            else:
                hours_per_unit = float(hours_input)

            if hours_per_unit <= 0:
                console.print("[bold red]Hours must be greater than zero[/bold red]")
                continue
            break
        except ValueError:
            console.print("[bold red]Please enter a valid number or fraction[/bold red]")

    scheduler.add_goal(slug, calendar_name, hours_per_unit)
    console.print(f"\n[bold green]✓ Added '{slug}' to scheduling as '{calendar_name}'[/bold green]")
    console.print(f"[dim]Time conversion: {hours_per_unit} hours per {units}[/dim]")
    prompt("\nPress Enter to continue... ")

def remove_goal_from_scheduling(scheduler: BeeminderScheduler) -> None:
    console.clear()
    console.print("[bold cyan]Remove Goal from Scheduling[/bold cyan]")

    scheduled_goals = scheduler.get_scheduled_goals()
    if not scheduled_goals:
        console.print("[bold yellow]No goals currently scheduled[/bold yellow]")
        prompt("\nPress Enter to continue... ")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Goal ID", style="dim")
    table.add_column("Calendar Name")
    table.add_column("Hours per Unit", justify="right")

    scheduled_list = list(scheduled_goals.items())
    for i, (slug, goal) in enumerate(scheduled_list, 1):
        table.add_row(
            str(i),
            slug,
            goal.calendar_name,
            str(goal.hours_per_unit)
        )

    console.print(table)
    goal_numbers = [str(i) for i in range(len(scheduled_list) + 1)]
    goal_choice = prompt("\nSelect goal # to remove (or 0 to return to main menu): ",
                       completer=WordCompleter(goal_numbers))

    if goal_choice == "0" or not goal_choice.isdigit():
        return

    goal_index = int(goal_choice) - 1
    if goal_index < 0 or goal_index >= len(scheduled_list):
        console.print("[bold red]Invalid selection![/bold red]")
        prompt("\nPress Enter to continue... ")
        return

    slug = scheduled_list[goal_index][0]
    console.print(f"\n[yellow]Are you sure you want to remove '{slug}' from scheduling?[/yellow]")
    confirm = prompt("Type 'yes' to confirm: ", completer=WordCompleter(['yes', 'no']))

    if confirm.lower() != "yes":
        console.print("[yellow]Removal canceled.[/yellow]")
        prompt("\nPress Enter to continue... ")
        return

    scheduler.remove_goal(slug)
    console.print(f"\n[bold green]✓ Removed '{slug}' from scheduling[/bold green]")
    prompt("\nPress Enter to continue... ")

def edit_goal_settings(api: BeeminderAPI, scheduler: BeeminderScheduler) -> None:
    console.clear()
    console.print("[bold cyan]Edit Goal Settings[/bold cyan]")

    scheduled_goals = scheduler.get_scheduled_goals()
    if not scheduled_goals:
        console.print("[bold yellow]No goals currently scheduled[/bold yellow]")
        prompt("\nPress Enter to continue... ")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Goal ID", style="dim")
    table.add_column("Calendar Name")
    table.add_column("Hours per Unit", justify="right")

    scheduled_list = list(scheduled_goals.items())
    for i, (slug, goal) in enumerate(scheduled_list, 1):
        table.add_row(
            str(i),
            slug,
            goal.calendar_name,
            str(goal.hours_per_unit)
        )

    console.print(table)
    goal_numbers = [str(i) for i in range(len(scheduled_list) + 1)]
    goal_choice = prompt("\nSelect goal # to edit (or 0 to return to main menu): ",
                       completer=WordCompleter(goal_numbers))

    if goal_choice == "0" or not goal_choice.isdigit():
        return

    goal_index = int(goal_choice) - 1
    if goal_index < 0 or goal_index >= len(scheduled_list):
        console.print("[bold red]Invalid selection![/bold red]")
        prompt("\nPress Enter to continue... ")
        return

    slug, goal = scheduled_list[goal_index]
    try:
        goal_data = api.get_goal(slug)
        units = goal_data.get('gunits', 'units')
    except:
        units = 'units'

    console.print(f"\n[bold]Editing:[/bold] {slug}")
    console.print(f"[dim]Current calendar name:[/dim] {goal.calendar_name}")
    console.print(f"[dim]Current conversion:[/dim] {goal.hours_per_unit} hours per {units}")

    console.print("\n[dim]Leave blank to keep current value[/dim]")
    calendar_name = prompt(f"New calendar name: ", completer=WordCompleter([goal.calendar_name]))

    hours_per_unit = None
    current_value = str(goal.hours_per_unit)
    hour_suggestions = [current_value, '1.0', '0.5', '0.25', '2.0']
    hours_input = prompt(f"New hours per {units} value: ", completer=WordCompleter(hour_suggestions))

    if hours_input:
        try:
            if '/' in hours_input:
                numerator, denominator = hours_input.split('/', 1)
                try:
                    hours_per_unit = float(numerator.strip()) / float(denominator.strip())
                except (ValueError, ZeroDivisionError):
                    console.print("[bold red]Invalid fraction format, ignoring this change[/bold red]")
                    hours_per_unit = None
            else:
                hours_per_unit = float(hours_input)

            if hours_per_unit is not None and hours_per_unit <= 0:
                console.print("[bold red]Hours must be greater than zero, ignoring this change[/bold red]")
                hours_per_unit = None
        except ValueError:
            console.print("[bold red]Invalid number or fraction, ignoring this change[/bold red]")

    if calendar_name or hours_per_unit is not None:
        scheduler.update_goal(slug,
                            calendar_name if calendar_name else None,
                            hours_per_unit)
        console.print(f"\n[bold green]✓ Updated '{slug}' settings[/bold green]")
    else:
        console.print("\n[yellow]No changes were made[/yellow]")

    prompt("\nPress Enter to continue... ")
