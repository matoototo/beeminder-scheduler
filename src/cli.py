"""
Beeminder Scheduler CLI
Interactive command-line interface for the Beeminder Scheduler
"""

import os
import json
import click
from typing import Dict

from beeminder_api import BeeminderAPI
from scheduler import BeeminderScheduler
from ui import console, get_credentials, display_goals, display_scheduled_goals, display_requirements, display_schedule
from interactive import start_interactive_mode
from llm_scheduler import LLMScheduler
from google_calendar import GoogleCalendarAPI, setup_google_calendar

CONFIG_FILE = os.path.expanduser("~/.beeminder-schedule.json")

def load_config() -> Dict:
    """Load config from file"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_config(config: Dict) -> None:
    """Save config to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

@click.group()
def cli():
    """Beeminder Scheduler - Create calendar events from Beeminder goals"""
    pass

# Global flag to show config file path
@cli.command(help="Show config file path and exit")
def where():
    """Show configuration file location and exit"""
    console.print(f"Configuration file: [bold]{CONFIG_FILE}[/bold]")

@cli.command()
def setup():
    """Set up Beeminder credentials"""
    username, auth_token = get_credentials(CONFIG_FILE)
    if username and auth_token:
        console.print("[bold green]✓ Setup complete![/bold green]")

@cli.command()
def goals():
    """List all Beeminder goals"""
    username, auth_token = get_credentials(CONFIG_FILE)
    if not username or not auth_token:
        return

    api = BeeminderAPI(username, auth_token)
    scheduler = BeeminderScheduler(api)

    try:
        console.print("[bold]Fetching your Beeminder goals...[/bold]")
        all_goals = api.get_goals()
        scheduled_goals = scheduler.get_scheduled_goals()
        display_goals(all_goals, scheduled_goals)

    except Exception as e:
        console.print(f"[bold red]❌ Error fetching goals: {e}[/bold red]")

@cli.command()
def scheduled():
    """List goals configured for scheduling"""
    username, auth_token = get_credentials(CONFIG_FILE)
    if not username or not auth_token:
        return

    api = BeeminderAPI(username, auth_token)
    scheduler = BeeminderScheduler(api)

    try:
        goals = scheduler.get_scheduled_goals()
        display_scheduled_goals(goals)

    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")

@cli.command()
@click.argument('slug')
@click.option('--name', help='Calendar event name')
@click.option('--hours', type=float, help='Hours per unit')
def add(slug, name, hours):
    """Add a goal to the scheduling system"""
    username, auth_token = get_credentials(CONFIG_FILE)
    if not username or not auth_token:
        return

    api = BeeminderAPI(username, auth_token)
    scheduler = BeeminderScheduler(api)

    try:
        # Verify goal exists
        try:
            api.get_goal(slug)
        except:
            console.print(f"[bold red]❌ Goal '{slug}' not found on Beeminder[/bold red]")
            return

        calendar_name = name or slug
        hours_per_unit = hours or 1.0

        scheduler.add_goal(slug, calendar_name, hours_per_unit)
        console.print(f"[bold green]✓ Added '{slug}' to scheduling as '{calendar_name}'[/bold green]")
        console.print(f"[dim]Time conversion: {hours_per_unit} hours per unit[/dim]")
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")

@cli.command()
@click.argument('slug')
def remove(slug):
    """Remove a goal from scheduling"""
    username, auth_token = get_credentials(CONFIG_FILE)
    if not username or not auth_token:
        return

    api = BeeminderAPI(username, auth_token)
    scheduler = BeeminderScheduler(api)

    try:
        scheduler.remove_goal(slug)
        console.print(f"[bold green]✓ Removed '{slug}' from scheduling[/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")

@cli.command()
def requirements():
    """Show scheduling requirements for today"""
    username, auth_token = get_credentials(CONFIG_FILE)
    if not username or not auth_token:
        return

    api = BeeminderAPI(username, auth_token)
    scheduler = BeeminderScheduler(api)

    try:
        requirements_data = scheduler.calculate_requirements()
        display_requirements(requirements_data)
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")

@cli.command()
def config():
    """Show the path to the configuration file"""
    console.print(f"Configuration file: [bold]{CONFIG_FILE}[/bold]")

    if os.path.exists(CONFIG_FILE):
        console.print(f"[green]✓ Configuration file exists[/green]")

        # Show some basic info about the config
        try:
            config = load_config()
            username = config.get('username')
            num_goals = len(config.get('goals', {}))

            if username:
                console.print(f"- Configured for user: [cyan]{username}[/cyan]")

            console.print(f"- Scheduled goals: [cyan]{num_goals}[/cyan]")
        except:
            console.print("[yellow]⚠ Could not read configuration details[/yellow]")
    else:
        console.print(f"[yellow]⚠ Configuration file does not exist yet[/yellow]")
        console.print(f"[dim]Run the setup command or add a goal to create the configuration file[/dim]")

@cli.command()
def interactive():
    """Launch interactive mode"""
    username, auth_token = get_credentials(CONFIG_FILE)
    if not username or not auth_token:
        return

    api = BeeminderAPI(username, auth_token)
    scheduler = BeeminderScheduler(api)

    try:
        start_interactive_mode(api, scheduler)
    except KeyboardInterrupt:
        console.print("\n[yellow]Exiting interactive mode...[/yellow]")
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")

@cli.command()
@click.option('--start-time', '-s', help='Start time for the schedule (e.g., "9:00 AM")')
@click.option('--end-time', '-e', help='End time for the schedule (optional)')
@click.option('--preferences', '-p', help='Special preferences or context for scheduling')
def schedule(start_time, end_time, preferences):
    """Generate a daily schedule from Beeminder goals"""
    username, auth_token = get_credentials(CONFIG_FILE)
    if not username or not auth_token:
        return

    api = BeeminderAPI(username, auth_token)
    scheduler = BeeminderScheduler(api)
    llm_scheduler = LLMScheduler(api, scheduler)

    # Default start time to current rounded time if not provided
    if not start_time:
        from datetime import datetime
        now = datetime.now()
        minutes = now.minute
        rounded_minutes = ((minutes + 14) // 15) * 15
        if rounded_minutes >= 60:
            rounded_time = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)
        else:
            rounded_time = now.replace(minute=rounded_minutes, second=0, microsecond=0)
        start_time = rounded_time.strftime("%I:%M %p").lstrip('0')
        console.print(f"[dim]Using default start time: {start_time}[/dim]")

    try:
        console.print("[bold]Fetching your Beeminder requirements...[/bold]")
        requirements = scheduler.calculate_requirements()

        if not requirements:
            console.print("[bold yellow]No scheduled goals found.[/bold yellow]")
            console.print("[dim]Add goals for scheduling first before generating a schedule.[/dim]")
            return

        console.print(f"[dim]Found {len(requirements)} goals to schedule[/dim]")

        # Check if API key is configured
        api_key = llm_scheduler.config.get('api_key', '')
        if not api_key:
            console.print("[yellow]API key not set up yet.[/yellow]")
            api_key = llm_scheduler.setup_api_key()
            if not api_key:
                return

        console.print("[bold]Generating your schedule...[/bold]")
        schedule_text = llm_scheduler.generate_schedule(
            requirements,
            start_time,
            end_time,
            preferences or ""
        )

        display_schedule(schedule_text)

    except Exception as e:
        console.print(f"[bold red]❌ Error generating schedule: {e}[/bold red]")

# New Google Calendar commands
@cli.group()
def gcal():
    """Google Calendar integration"""
    pass

@gcal.command()
def setup():
    """Set up Google Calendar integration"""
    console.print("[bold cyan]Google Calendar Setup[/bold cyan]")
    setup_google_calendar()

@gcal.command()
def calendars():
    """List available Google Calendars"""
    api = GoogleCalendarAPI()
    if not api.authenticate():
        console.print("[bold red]❌ Failed to authenticate with Google Calendar[/bold red]")
        return

    calendars = api.get_calendar_list()

    if not calendars:
        console.print("[yellow]No calendars found[/yellow]")
        return

    console.print("[bold]Your Google Calendars:[/bold]")

    from rich.table import Table
    from rich import box

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Calendar ID", style="dim")
    table.add_column("Name", style="bold")
    table.add_column("Primary", justify="center")

    for i, calendar in enumerate(calendars, 1):
        table.add_row(
            str(i),
            calendar.get('id', ''),
            calendar.get('summary', ''),
            "✓" if calendar.get('primary', False) else ""
        )

    console.print(table)

    # Save primary calendar ID for future use
    config = load_config()
    primary_calendars = [cal for cal in calendars if cal.get('primary', False)]

    if primary_calendars and not config.get('google_calendar_id'):
        primary_id = primary_calendars[0].get('id')
        config['google_calendar_id'] = primary_id
        save_config(config)
        console.print(f"[green]✓ Saved primary calendar as default: {primary_id}[/green]")

@gcal.command()
@click.option('--calendar-id', '-c', help='Google Calendar ID to use')
def push(calendar_id):
    """Push the last generated schedule to Google Calendar"""
    # Get the last generated schedule
    from interactive import get_last_schedule

    schedule_text = get_last_schedule()
    if not schedule_text:
        console.print("[yellow]No recently generated schedule found[/yellow]")
        console.print("[dim]Generate a schedule first using the 'schedule' command[/dim]")
        return

    # Get calendar ID
    if not calendar_id:
        config = load_config()
        calendar_id = config.get('google_calendar_id')

        if not calendar_id:
            console.print("[yellow]No default calendar ID set[/yellow]")
            console.print("[dim]Run 'gcal calendars' to set a default or specify with --calendar-id[/dim]")
            return

    api = GoogleCalendarAPI()
    if not api.authenticate():
        console.print("[bold red]❌ Failed to authenticate with Google Calendar[/bold red]")
        return

    console.print("[bold]Pushing schedule to Google Calendar...[/bold]")
    events_created, errors = api.push_schedule_to_calendar(schedule_text, calendar_id)

    if events_created > 0:
        console.print(f"[bold green]✓ Successfully created {events_created} calendar events![/bold green]")

    if errors:
        console.print("[yellow]The following errors occurred:[/yellow]")
        for error in errors:
            console.print(f"- {error}")

@cli.command()
@click.option('--start-time', '-s', help='Start time for the schedule (e.g., "9:00 AM")')
@click.option('--end-time', '-e', help='End time for the schedule (optional)')
@click.option('--preferences', '-p', help='Special preferences or context for scheduling')
@click.option('--push-to-calendar', '-c', is_flag=True, help='Push schedule to Google Calendar')
@click.option('--calendar-id', help='Google Calendar ID to use')
def today(start_time, end_time, preferences, push_to_calendar, calendar_id):
    """Generate a schedule and optionally push to Google Calendar"""
    username, auth_token = get_credentials(CONFIG_FILE)
    if not username or not auth_token:
        return

    api = BeeminderAPI(username, auth_token)
    scheduler = BeeminderScheduler(api)
    llm_scheduler = LLMScheduler(api, scheduler)

    # Default start time to current rounded time if not provided
    if not start_time:
        from datetime import datetime
        now = datetime.now()
        minutes = now.minute
        rounded_minutes = ((minutes + 14) // 15) * 15
        if rounded_minutes >= 60:
            rounded_time = now.replace(hour=now.hour + 1, minute=0, second=0, microsecond=0)
        else:
            rounded_time = now.replace(minute=rounded_minutes, second=0, microsecond=0)
        start_time = rounded_time.strftime("%I:%M %p").lstrip('0')
        console.print(f"[dim]Using default start time: {start_time}[/dim]")

    try:
        console.print("[bold]Fetching your Beeminder requirements...[/bold]")
        requirements = scheduler.calculate_requirements()

        if not requirements:
            console.print("[bold yellow]No scheduled goals found.[/bold yellow]")
            console.print("[dim]Add goals for scheduling first before generating a schedule.[/dim]")
            return

        console.print(f"[dim]Found {len(requirements)} goals to schedule[/dim]")

        # Check if API key is configured
        api_key = llm_scheduler.config.get('api_key', '')
        if not api_key:
            console.print("[yellow]API key not set up yet.[/yellow]")
            api_key = llm_scheduler.setup_api_key()
            if not api_key:
                return

        console.print("[bold]Generating your schedule...[/bold]")
        schedule_text = llm_scheduler.generate_schedule(
            requirements,
            start_time,
            end_time,
            preferences or ""
        )

        from interactive import save_last_schedule
        save_last_schedule(schedule_text)

        display_schedule(schedule_text)

        # Push to Google Calendar if requested
        if push_to_calendar:
            # Get calendar ID
            if not calendar_id:
                config = load_config()
                calendar_id = config.get('google_calendar_id')

                if not calendar_id:
                    console.print("[yellow]No default calendar ID set[/yellow]")
                    console.print("[dim]Run 'gcal calendars' to set a default or specify with --calendar-id[/dim]")
                    return

            api = GoogleCalendarAPI()
            if not api.authenticate():
                console.print("[bold red]❌ Failed to authenticate with Google Calendar[/bold red]")
                return

            console.print("[bold]Pushing schedule to Google Calendar...[/bold]")
            events_created, errors = api.push_schedule_to_calendar(schedule_text, calendar_id)

            if events_created > 0:
                console.print(f"[bold green]✓ Successfully created {events_created} calendar events![/bold green]")

            if errors:
                console.print("[yellow]The following errors occurred:[/yellow]")
                for error in errors:
                    console.print(f"- {error}")

    except Exception as e:
        console.print(f"[bold red]❌ Error generating schedule: {e}[/bold red]")

if __name__ == '__main__':
    cli()
