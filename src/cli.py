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
from ui import console, get_credentials, display_goals, display_scheduled_goals, display_requirements
from interactive import start_interactive_mode

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

if __name__ == '__main__':
    cli()
