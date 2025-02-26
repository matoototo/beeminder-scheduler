"""
UI Utilities for Beeminder Scheduler
Common UI components and display functions
"""

import os
import json
from typing import Dict, List
from datetime import datetime
import colorama
from prompt_toolkit import prompt
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from beeminder_api import BeeminderAPI

# Initialize colorama for cross-platform colors
colorama.init()

# Setup rich console
console = Console()

def get_credentials(config_file: str) -> tuple:
    """Get credentials from config or prompt"""
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {}

    username = config.get('username')
    auth_token = config.get('auth_token')

    if not username or not auth_token:
        console.print(Panel(
            "[bold]Welcome to Beeminder Scheduler![/bold]\n\n"
            "To get started, you'll need to provide your Beeminder credentials.\n"
            "Your auth token can be found at [link=https://www.beeminder.com/settings/account#account-permissions]https://www.beeminder.com/settings/account[/link]\n"
            "Look for the 'Personal Auth Token' section.",
            title="Setup",
            border_style="blue"
        ))

        username = prompt("Beeminder username: ")
        auth_token = prompt("Beeminder auth token: ")

        # Test credentials
        api = BeeminderAPI(username, auth_token)
        if not api.test_auth():
            console.print("[bold red]❌ Authentication failed. Please check your credentials.[/bold red]")
            return None, None

        config['username'] = username
        config['auth_token'] = auth_token

        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        console.print("[bold green]✓ Authentication successful! Your credentials have been saved.[/bold green]")

    return username, auth_token

def display_goals(all_goals: List[Dict], scheduled_goals: Dict) -> None:
    """Display all goals in a rich table"""
    if not all_goals:
        console.print("[yellow]No goals found[/yellow]")
        return

    # Prepare rich table
    table = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("ID", style="dim", width=12)
    table.add_column("Title", min_width=20)
    table.add_column("Progress", justify="right")
    table.add_column("Deadline", justify="center")
    table.add_column("Scheduled", justify="center")

    for goal in all_goals:
        slug = goal.get('slug')
        title = goal.get('title', '')

        current = f"{goal.get('curval', 0):.1f}"
        target = f"{goal.get('goalval', 0):.1f}"
        units = goal.get('gunits', '')

        deadline = datetime.fromtimestamp(goal.get('losedate', 0))
        days_left = (deadline - datetime.now()).days

        # Format deadline with color based on urgency
        if days_left < 1:
            deadline_str = f"[bold red]{deadline.strftime('%Y-%m-%d')}[/bold red]"
        elif days_left < 3:
            deadline_str = f"[yellow]{deadline.strftime('%Y-%m-%d')}[/yellow]"
        else:
            deadline_str = deadline.strftime("%Y-%m-%d")

        # Show if goal is scheduled
        scheduled_str = f"[bold green]✓[/bold green]" if slug in scheduled_goals else ""

        table.add_row(
            slug,
            title,
            f"{current}/{target} {units}",
            deadline_str,
            scheduled_str
        )

    console.print(table)

def display_scheduled_goals(goals: Dict) -> None:
    """Display scheduled goals in a rich table"""
    if not goals:
        console.print("[yellow]No goals configured for scheduling yet.[/yellow]")
        console.print("[dim]Use the 'add' command to add goals for scheduling.[/dim]")
        return

    # Prepare rich table
    table = Table(
        title="Scheduled Goals",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Goal ID", style="dim")
    table.add_column("Calendar Name", style="bold")
    table.add_column("Time Conversion", justify="right")

    for slug, goal in goals.items():
        table.add_row(
            slug,
            goal.calendar_name,
            f"{goal.hours_per_unit} hours per unit"
        )

    console.print(table)

def display_requirements(requirements: Dict) -> None:
    if not requirements:
        console.print("[yellow]No scheduled goals found[/yellow]")
        return

    table = Table(title="Units Needed Today", box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Activity", style="bold")
    table.add_column("Units Needed", justify="right")
    table.add_column("Hours Needed", justify="right")
    table.add_column("Deadline", justify="center")
    table.add_column("Safe Days", justify="center")
    table.add_column("Pledge", justify="right")
    table.add_column("Beeminder Says", justify="left")
    table.add_column("Hours/Day", justify="right")

    total_hours = 0
    for slug, data in requirements.items():
        if data.get('missing_data', False):
            continue
        deadline_str = data['deadline'].strftime("%Y-%m-%d")
        hours = data['hours_needed']
        total_hours += hours
        row = [
            data['calendar_name'],
            f"{data.get('delta', 0):.1f}",  # Use 'delta' instead of 'units_needed'
            f"{hours:.1f}",
            deadline_str,
            f"{data['safebuf']}",
            f"${data['pledge']}",
            data['limsum']
        ]
        row.append(f"{data['hours_per_day']:.1f}")
        table.add_row(*row, style="red" if data['safebuf'] == 0 else None)

    console.print(table)
    console.print(f"[bold]Total hours needed today:[/bold] [cyan]{total_hours:.1f}[/cyan]")
