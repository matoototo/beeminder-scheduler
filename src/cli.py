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
        console.print(f"[bold red]❌ Error: {e}[/bold red]")#!/usr/bin/env python3

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

if __name__ == '__main__':
    cli()
