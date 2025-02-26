"""
Interactive mode for Beeminder Scheduler
Implements the interactive menu system
"""

from datetime import datetime
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from rich.panel import Panel
from rich.table import Table
from rich import box

from beeminder_api import BeeminderAPI
from scheduler import BeeminderScheduler
from ui import console

def start_interactive_mode(api: BeeminderAPI, scheduler: BeeminderScheduler) -> None:
    """Start the interactive menu system"""
    try:
        # Show config location in a more visually clear way
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
    """Show and handle the interactive menu"""
    while True:
        console.clear()

        # Create header with config info
        header_text = (
            "[bold cyan]Beeminder Scheduler[/bold cyan]\n"
            "[dim]Integrate your Beeminder goals with your calendar[/dim]\n\n"
            f"[dim]Config: [bold]{scheduler.config_file}[/bold] "
        )
        console.print(Panel(
            header_text,
            border_style="blue"
        ))

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
                    f"{goal.hours_per_unit}"  # Ensure this is a string before formatting
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
        console.print("0. [white]Exit[/white]")

        # Create a word completer for menu choices
        menu_completer = WordCompleter(['0', '1', '2', '3', '4', '5'])
        choice = prompt("\nEnter your choice (0-5): ", completer=menu_completer)

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
        else:
            console.print("[bold red]Invalid choice![/bold red]")
            prompt("\nPress Enter to continue... ")

def show_scheduling_requirements(scheduler: BeeminderScheduler) -> None:
    """Show scheduling requirements"""
    console.clear()
    console.print("[bold cyan]Scheduling Requirements[/bold cyan]")

    # Ask for days to look ahead with autocompletion
    days_completer = WordCompleter(['7', '14', '30', '90'])
    days_input = prompt("Days to look ahead [7]: ", completer=days_completer)
    days = 7
    if days_input and days_input.isdigit():
        days = int(days_input)

    console.print(f"[dim]Calculating requirements for the next {days} days...[/dim]")

    # Get requirements
    requirements = scheduler.calculate_requirements(days_ahead=days)

    if not requirements:
        console.print("[bold yellow]No scheduled goals found[/bold yellow]")
        prompt("\nPress Enter to continue... ")
        return

    # Display requirements in a table
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

        # Use the urgency level for styling
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

    # Show summary
    console.print(f"\n[bold]Total hours needed:[/bold] [cyan]{total_hours:.1f}[/cyan]")
    console.print(f"[bold]Average hours per day:[/bold] [cyan]{(total_hours/days):.1f}[/cyan]")

    # Add explanation of colors
    console.print("\n[dim]Note: [red]Red rows[/red] indicate goals with deadlines within the next {days} days[/dim]")

    prompt("\nPress Enter to continue... ")

def view_all_goals(api: BeeminderAPI, scheduler: BeeminderScheduler) -> None:
    """View all Beeminder goals"""
    console.clear()
    console.print("[bold cyan]All Beeminder Goals[/bold cyan]")

    # Fetch all goals and create a lookup of scheduled ones
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

        # Format the deadline with appropriate color
        deadline = datetime.fromtimestamp(goal.get('losedate', 0))
        days_left = (deadline - datetime.now()).days

        if days_left < 1:
            deadline_str = f"[bold red]{deadline.strftime('%Y-%m-%d')}[/bold red]"
        elif days_left < 3:
            deadline_str = f"[yellow]{deadline.strftime('%Y-%m-%d')}[/yellow]"
        else:
            deadline_str = deadline.strftime("%Y-%m-%d")

        # Show if goal is scheduled
        scheduled_str = "[bold green]✓[/bold green]" if slug in scheduled_slugs else ""

        # Safely format the progress
        curval = goal.get('curval')
        goalval = goal.get('goalval')
        gunits = goal.get('gunits', '')

        # Handle cases where curval or goalval might be None
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
    """Add a goal to scheduling"""
    console.clear()
    console.print("[bold cyan]Add Goal to Scheduling[/bold cyan]")

    # Get all goals and filter out already scheduled ones
    all_goals = api.get_goals()
    scheduled_goals = scheduler.get_scheduled_goals()
    scheduled_slugs = set(scheduled_goals.keys())
    available_goals = [g for g in all_goals if g['slug'] not in scheduled_slugs]

    if not available_goals:
        console.print("[bold yellow]All goals are already scheduled![/bold yellow]")
        prompt("\nPress Enter to continue... ")
        return

    # Show available goals in a nice table
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

    # Create a completer with available goal numbers
    goal_numbers = [str(i) for i in range(len(available_goals) + 1)]  # Include 0 for return
    goal_completer = WordCompleter(goal_numbers)

    # Get user selection with autocomplete
    goal_choice = prompt("\nSelect goal # to add (or 0 to return to main menu): ", completer=goal_completer)
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

    # Show info about the goal
    console.print(f"\n[bold]Selected:[/bold] {slug} - {title}")

    # Get calendar name with nice description
    console.print("\n[dim]The calendar name is what will appear in your calendar events.[/dim]")

    # Create a completer with the title as a suggestion
    name_completer = WordCompleter([title])
    calendar_name = prompt(f"Calendar event name [{title}]: ", completer=name_completer)
    if not calendar_name:
        calendar_name = title

    # Get hours per unit with explanation
    units = selected_goal.get('gunits', 'units')
    console.print(f"\n[dim]How many hours does each {units} of this goal take?[/dim]")
    console.print(f"[dim]Examples:[/dim]")
    console.print(f"[dim]- Reading goal: 2 hours per 40 pages = 0.05 hours per page[/dim]")
    console.print(f"[dim]- Coding goal: 3 hours per 1 commit = 3 hours per commit[/dim]")

    while True:
        hours_input = prompt(f"Hours per {units} [1.0] (can use fractions like 1/20): ")
        if not hours_input:
            hours_per_unit = 1.0
            break

        try:
            # Check if input contains a fraction
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

    # Add the goal with a confirmation
    scheduler.add_goal(slug, calendar_name, hours_per_unit)
    console.print(f"\n[bold green]✓ Added '{slug}' to scheduling as '{calendar_name}'[/bold green]")
    console.print(f"[dim]Time conversion: {hours_per_unit} hours per {units}[/dim]")
    prompt("\nPress Enter to continue... ")

def remove_goal_from_scheduling(scheduler: BeeminderScheduler) -> None:
    """Remove a goal from scheduling"""
    console.clear()
    console.print("[bold cyan]Remove Goal from Scheduling[/bold cyan]")

    scheduled_goals = scheduler.get_scheduled_goals()
    if not scheduled_goals:
        console.print("[bold yellow]No goals currently scheduled[/bold yellow]")
        prompt("\nPress Enter to continue... ")
        return

    # Show scheduled goals
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

    # Create a completer with available goal numbers
    goal_numbers = [str(i) for i in range(len(scheduled_list) + 1)]  # Include 0 for return
    goal_completer = WordCompleter(goal_numbers)

    # Get user selection with autocomplete
    goal_choice = prompt("\nSelect goal # to remove (or 0 to return to main menu): ", completer=goal_completer)
    if goal_choice == "0" or not goal_choice.isdigit():
        return

    goal_index = int(goal_choice) - 1
    if goal_index < 0 or goal_index >= len(scheduled_list):
        console.print("[bold red]Invalid selection![/bold red]")
        prompt("\nPress Enter to continue... ")
        return

    slug = scheduled_list[goal_index][0]

    # Confirm deletion
    console.print(f"\n[yellow]Are you sure you want to remove '{slug}' from scheduling?[/yellow]")
    confirm_completer = WordCompleter(['yes', 'no'])
    confirm = prompt("Type 'yes' to confirm: ", completer=confirm_completer)

    if confirm.lower() != "yes":
        console.print("[yellow]Removal canceled.[/yellow]")
        prompt("\nPress Enter to continue... ")
        return

    # Remove the goal
    scheduler.remove_goal(slug)
    console.print(f"\n[bold green]✓ Removed '{slug}' from scheduling[/bold green]")
    prompt("\nPress Enter to continue... ")

def edit_goal_settings(api: BeeminderAPI, scheduler: BeeminderScheduler) -> None:
    """Edit the settings of a scheduled goal"""
    console.clear()
    console.print("[bold cyan]Edit Goal Settings[/bold cyan]")

    scheduled_goals = scheduler.get_scheduled_goals()
    if not scheduled_goals:
        console.print("[bold yellow]No goals currently scheduled[/bold yellow]")
        prompt("\nPress Enter to continue... ")
        return

    # Show scheduled goals
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

    # Create a completer with available goal numbers
    goal_numbers = [str(i) for i in range(len(scheduled_list) + 1)]  # Include 0 for return
    goal_completer = WordCompleter(goal_numbers)

    # Get user selection with autocomplete
    goal_choice = prompt("\nSelect goal # to edit (or 0 to return to main menu): ", completer=goal_completer)
    if goal_choice == "0" or not goal_choice.isdigit():
        return

    goal_index = int(goal_choice) - 1
    if goal_index < 0 or goal_index >= len(scheduled_list):
        console.print("[bold red]Invalid selection![/bold red]")
        prompt("\nPress Enter to continue... ")
        return

    slug, goal = scheduled_list[goal_index]

    # Get goal details for better UX
    try:
        goal_data = api.get_goal(slug)
        units = goal_data.get('gunits', 'units')
    except:
        units = 'units'

    # Show current settings
    console.print(f"\n[bold]Editing:[/bold] {slug}")
    console.print(f"[dim]Current calendar name:[/dim] {goal.calendar_name}")
    console.print(f"[dim]Current conversion:[/dim] {goal.hours_per_unit} hours per {units}")

    # Get new calendar name
    console.print("\n[dim]Leave blank to keep current value[/dim]")
    name_completer = WordCompleter([goal.calendar_name])
    calendar_name = prompt(f"New calendar name: ", completer=name_completer)

    # Get new hours per unit
    hours_per_unit = None

    # Create suggestions including the current value and common fractions
    current_value = str(goal.hours_per_unit)
    hour_suggestions = [current_value, '1.0', '0.5', '0.25', '2.0', '1/4', '1/2', '1/10', '1/20', '1/60']
    hours_completer = WordCompleter(hour_suggestions)

    hours_input = prompt(f"New hours per {units} value (can use fractions like 1/20): ", completer=hours_completer)

    if hours_input:
        try:
            # Check if input contains a fraction
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

    # Update only if values were provided
    if calendar_name or hours_per_unit is not None:
        scheduler.update_goal(slug,
                            calendar_name if calendar_name else None,
                            hours_per_unit)

        console.print(f"\n[bold green]✓ Updated '{slug}' settings[/bold green]")
    else:
        console.print("\n[yellow]No changes were made[/yellow]")

    prompt("\nPress Enter to continue... ")
