"""
LLM Scheduler for Beeminder
Integrates with Gemini API to generate daily schedules based on Beeminder goals
"""

import os
import json
import re
from typing import Dict, List, Optional
from datetime import datetime
import textwrap

from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter

from beeminder_api import BeeminderAPI
from scheduler import BeeminderScheduler

console = Console()

class LLMScheduler:
    def __init__(self, beeminder_api: BeeminderAPI, beeminder_scheduler: BeeminderScheduler,
                config_file: Optional[str] = None):
        self.beeminder_api = beeminder_api
        self.beeminder_scheduler = beeminder_scheduler
        self.config_file = config_file or os.path.expanduser("~/.beeminder-llm.json")
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {'api_key': '', 'default_prompt': self._get_default_prompt()}

    def _save_config(self) -> None:
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def _get_default_prompt(self) -> str:
        return textwrap.dedent("""\
            You are a scheduling assistant that creates daily schedules based on Beeminder goals.
            Create a realistic, hour-by-hour schedule for TODAY based on the requirements.

            Guidelines:
            1. Allocate time for each goal based on the hours needed
            2. Create a balanced schedule with breaks and transitions
            3. Prioritize activities with closer deadlines or higher pledges
            4. If there's not enough time for all goals, prioritize and explain why

            YOU MUST FOLLOW THIS EXACT FORMAT:

            ```schedule
            START_TIME - END_TIME: ACTIVITY_NAME (GOAL_NAME)
            START_TIME - END_TIME: ACTIVITY_NAME (GOAL_NAME)
            ...
            ```

            Example:
            ```schedule
            8:00 AM - 9:30 AM: Morning coding session (Programming)
            9:30 AM - 9:45 AM: Break
            9:45 AM - 11:15 AM: Continue coding (Programming)
            11:15 AM - 12:00 PM: Read documentation (Reading)
            12:00 PM - 1:00 PM: Lunch break
            ```

            After the schedule, include a section titled "Notes:" with a brief explanation.

            ALL TIMES must be in HH:MM AM/PM format (e.g., "8:00 AM").
            For Beeminder goals, include the goal name in parentheses.
            For breaks or other activities, parentheses are not needed.
        """)

    def setup_api_key(self) -> str:
        api_key = self.config.get('api_key', '')

        if not api_key:
            console.print(Panel(
                "[bold]LLM Integration Setup[/bold]\n\n"
                "To generate schedules, you'll need to provide a Gemini API key.\n"
                "You can get one from [link=https://aistudio.google.com/app/apikey]Google AI Studio[/link].",
                title="API Setup",
                border_style="blue"
            ))

            api_key = prompt("Gemini API key: ", is_password=True)
            self.config['api_key'] = api_key
            self._save_config()

            if not self._test_api_key(api_key):
                console.print("[bold red]❌ Invalid API key. Please try again.[/bold red]")
                return ''

            console.print("[bold green]✓ API key verified and saved.[/bold green]")

        return api_key

    def _test_api_key(self, api_key: str) -> bool:
        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )

            client.chat.completions.create(
                model="gemini-2.0-flash",
                messages=[
                    {"role": "system", "content": "Hello"},
                    {"role": "user", "content": "Test"}
                ],
                max_tokens=10
            )
            return True
        except Exception as e:
            console.print(f"[dim]Error testing API key: {e}[/dim]")
            return False

    def edit_prompt_template(self) -> None:
        current_prompt = self.config.get('default_prompt', self._get_default_prompt())

        console.print(Panel(
            "[bold]Edit Default Prompt Template[/bold]\n\n"
            "This is the system prompt that tells the LLM how to create schedules.",
            title="Prompt Editor",
            border_style="blue"
        ))

        console.print(Panel(current_prompt, title="Current Prompt", border_style="cyan"))

        edit_choice = prompt("\nDo you want to edit this prompt? (yes/no): ",
                           completer=WordCompleter(['yes', 'no']))

        if edit_choice.lower() != 'yes':
            return

        console.print("[dim]Enter your new prompt below. Press Enter twice on an empty line to finish.[/dim]")

        lines = []
        try:
            while True:
                line = prompt("> ")
                if not line and (not lines or not lines[-1]):
                    break
                lines.append(line)
        except KeyboardInterrupt:
            console.print("\n[yellow]Cancelled. No changes made.[/yellow]")
            return

        new_prompt = "\n".join(lines)
        if new_prompt.strip():
            self.config['default_prompt'] = new_prompt
            self._save_config()
            console.print("[bold green]✓ Prompt template updated.[/bold green]")
        else:
            console.print("[yellow]No changes made (empty prompt).[/yellow]")

    def generate_schedule(self, requirements: Dict, start_time: str,
                        end_time: Optional[str] = None, user_preferences: str = "") -> str:
        api_key = self.setup_api_key()
        if not api_key:
            return "API key setup failed. Cannot generate schedule."

        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = self.config.get('default_prompt', self._get_default_prompt())

        # Format only the essential data needed for scheduling
        goals_data = []
        for slug, data in requirements.items():
            goals_data.append({
                "name": data['calendar_name'],
                "hours": round(data['hours_needed'], 1),
                "deadline": data['deadline'].strftime("%Y-%m-%d"),
                "pledge": data['pledge']
            })

        # Create simple text-based prompt for better readability
        goals_text = "\n".join([
            f"- {g['name']}: {g['hours']} hours, deadline: {g['deadline']}, pledge: ${g['pledge']}"
            for g in goals_data
        ])

        user_prompt = f"Today's date: {current_date}\nStart time: {start_time}"
        if end_time:
            user_prompt += f", End time: {end_time}"

        user_prompt += f"\n\nGoals to schedule:\n{goals_text}"

        if user_preferences:
            user_prompt += f"\n\nSpecial preferences or notes:\n{user_preferences}"

        user_prompt += "\n\nPlease create a detailed schedule for today based on these goals."

        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )

            console.print("[dim]Generating schedule...[/dim]")

            response = client.chat.completions.create(
                model="gemini-2.0-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            raw_schedule = response.choices[0].message.content
            return self._parse_schedule(raw_schedule)

        except Exception as e:
            console.print(f"[bold red]❌ Error generating schedule: {e}[/bold red]")
            return f"Failed to generate schedule: {str(e)}"

    def _parse_schedule(self, raw_schedule: str) -> str:
        schedule_match = re.search(r'```schedule\n(.*?)\n```', raw_schedule, re.DOTALL)

        if not schedule_match:
            console.print("[yellow]Warning: Schedule format not detected. Returning raw output.[/yellow]")
            return raw_schedule

        schedule_lines = schedule_match.group(1).strip().split('\n')
        notes_match = re.search(r'Notes:(.*?)$', raw_schedule, re.DOTALL)
        notes_text = notes_match.group(1).strip() if notes_match else ""

        formatted_schedule = []
        for line in schedule_lines:
            if not line.strip():
                continue

            time_match = re.match(r'(\d{1,2}:\d{2} [AP]M) - (\d{1,2}:\d{2} [AP]M): (.*?)$', line)

            if time_match:
                start_time, end_time, activity = time_match.groups()
                formatted_schedule.append(f"{start_time} - {end_time}: {activity}")
            else:
                formatted_schedule.append(f"{line} [format?]")

        final_schedule = "# Today's Schedule\n\n"
        for line in formatted_schedule:
            final_schedule += f"- {line}\n"

        if notes_text:
            final_schedule += f"\n## Notes\n\n{notes_text}\n"

        return final_schedule

    def refine_schedule(self, original_schedule: str, feedback: str) -> str:
        api_key = self.config.get('api_key', '')
        if not api_key:
            return "API key not set up. Cannot refine schedule."

        system_prompt = textwrap.dedent("""\
            You are a scheduling assistant refining a schedule based on feedback.

            YOU MUST FOLLOW THIS EXACT FORMAT:

            ```schedule
            START_TIME - END_TIME: ACTIVITY_NAME (GOAL_NAME)
            START_TIME - END_TIME: ACTIVITY_NAME (GOAL_NAME)
            ...
            ```

            After the schedule, include a section titled "Notes:" with an explanation.

            ALL TIMES must be in HH:MM AM/PM format (e.g., "8:00 AM").
            For Beeminder goals, include the goal name in parentheses.
            For breaks or other activities, parentheses are not needed.
        """)

        schedule_lines = []
        for line in original_schedule.split('\n'):
            if line.strip().startswith('- '):
                schedule_lines.append(line.strip()[2:])

        schedule_text = '\n'.join(schedule_lines)

        user_prompt = (
            f"Here is the previous schedule:\n\n```schedule\n{schedule_text}\n```\n\n"
            f"Please refine this schedule based on this feedback:\n{feedback}\n\n"
            f"Return the schedule in the exact format specified with the ```schedule``` block."
        )

        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )

            console.print("[dim]Refining schedule...[/dim]")

            response = client.chat.completions.create(
                model="gemini-2.0-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            raw_refined_schedule = response.choices[0].message.content
            return self._parse_schedule(raw_refined_schedule)

        except Exception as e:
            console.print(f"[bold red]❌ Error refining schedule: {e}[/bold red]")
            return f"Failed to refine schedule: {str(e)}"
