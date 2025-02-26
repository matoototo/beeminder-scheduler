"""
Beeminder Scheduler
Core functionality for scheduling based on Beeminder goals
"""

import os
import json
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from beeminder_api import BeeminderAPI


@dataclass
class ScheduledGoal:
    """A goal configured for scheduling"""
    slug: str
    calendar_name: str
    hours_per_unit: float = 1.0  # How many hours per Beeminder unit


class BeeminderScheduler:
    """
    Manages the scheduling of Beeminder goals
    Handles the conversion of Beeminder units to calendar time
    """

    def __init__(self, api: BeeminderAPI, config_file: Optional[str] = None):
        """Initialize with a Beeminder API client"""
        self.api = api
        self.config_file = config_file or os.path.expanduser("~/.beeminder-schedule.json")
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return {'goals': {}, 'username': self.api.username}

    def _save_config(self) -> None:
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)

    def add_goal(self, slug: str, calendar_name: Optional[str] = None, hours_per_unit: float = 1.0) -> None:
        """Add a goal to be scheduled"""
        # Verify goal exists
        self.api.get_goal(slug)

        goals = self.config.setdefault('goals', {})
        goals[slug] = {
            'calendar_name': calendar_name or slug,
            'hours_per_unit': hours_per_unit
        }
        self._save_config()

    def remove_goal(self, slug: str) -> None:
        """Remove a goal from scheduling"""
        if slug in self.config.get('goals', {}):
            del self.config['goals'][slug]
            self._save_config()

    def update_goal(self, slug: str, calendar_name: Optional[str] = None, hours_per_unit: Optional[float] = None) -> None:
        """Update goal settings"""
        if slug not in self.config.get('goals', {}):
            raise ValueError(f"Goal '{slug}' is not scheduled")

        goal_config = self.config['goals'][slug]

        if calendar_name is not None:
            goal_config['calendar_name'] = calendar_name

        if hours_per_unit is not None:
            goal_config['hours_per_unit'] = hours_per_unit

        self._save_config()

    def get_scheduled_goals(self) -> Dict[str, ScheduledGoal]:
        """Get all goals configured for scheduling"""
        result = {}
        for slug, config in self.config.get('goals', {}).items():
            result[slug] = ScheduledGoal(
                slug=slug,
                calendar_name=config.get('calendar_name', slug),
                hours_per_unit=config.get('hours_per_unit', 1.0)
            )
        return result

    def calculate_requirements(self, days_ahead: int = 7) -> Dict[str, Dict]:
        """Calculate scheduling requirements for the configured goals"""
        scheduled_goals = self.get_scheduled_goals()
        result = {}

        for slug, goal in scheduled_goals.items():
            try:
                # Get detailed goal data including the road
                goal_data = self.api.get_goal(slug)

                # Get critical values
                losedate = goal_data.get('losedate', 0)
                deadline = datetime.fromtimestamp(losedate) if losedate else datetime.now() + timedelta(days=365)

                current_value = goal_data.get('curval')
                target_value = goal_data.get('goalval')
                safebuf = goal_data.get('safebuf', 0)  # Days of safety buffer

                # Handle missing values - if curval or goalval is None, we can't calculate requirements
                if current_value is None or target_value is None:
                    # Include basic information but mark that we couldn't calculate requirements
                    result[slug] = {
                        'calendar_name': goal.calendar_name,
                        'deadline': deadline,
                        'safebuf': safebuf,
                        'is_urgent': safebuf < days_ahead,
                        'urgency': self._get_urgency_level(safebuf),
                        'hours_needed': 0,
                        'hours_per_day': 0,
                        'delta': 0,
                        'pledge': goal_data.get('pledge', 0),
                        'units': goal_data.get('gunits', ''),
                        'limsum': goal_data.get('limsum', 'Missing datapoints'),
                        'missing_data': True
                    }
                    continue

                # Get more metadata
                rate = goal_data.get('rate', 0)
                pledge = goal_data.get('pledge', 0)
                runits = goal_data.get('runits', 'd')  # Rate units (y/m/w/d/h)
                yaw = goal_data.get('yaw', 1)  # +1/-1 = good side is above/below the line
                limsum = goal_data.get('limsum', '')  # Summary of what you need to do

                # Calculate delta based on goal type
                if yaw > 0:  # Do more goal (good side is above the line)
                    delta = max(0, target_value - current_value)
                else:  # Do less goal (good side is below the line)
                    delta = max(0, current_value - target_value)

                # Calculate hours needed
                hours_needed = delta * goal.hours_per_unit

                # Calculate hours per day considering runits
                # Convert rate to daily equivalent
                rate_per_day = rate
                if runits == 'y':
                    rate_per_day = rate / 365
                elif runits == 'm':
                    rate_per_day = rate / 30
                elif runits == 'w':
                    rate_per_day = rate / 7
                elif runits == 'h':
                    rate_per_day = rate * 24

                # Calculate daily requirement (hours)
                hours_per_day = abs(rate_per_day * goal.hours_per_unit)

                # Is this urgent?
                is_urgent = safebuf < days_ahead

                # Determine urgency level (colors in Beeminder)
                urgency = self._get_urgency_level(safebuf)

                result[slug] = {
                    'calendar_name': goal.calendar_name,
                    'current_value': current_value,
                    'target_value': target_value,
                    'delta': delta,
                    'deadline': deadline,
                    'safebuf': safebuf,
                    'is_urgent': is_urgent,
                    'urgency': urgency,
                    'hours_needed': hours_needed,
                    'hours_per_day': hours_per_day,
                    'pledge': pledge,
                    'units': goal_data.get('gunits', ''),
                    'rate': rate,
                    'rate_per_day': rate_per_day,
                    'limsum': limsum,
                    'missing_data': False
                }
            except Exception as e:
                print(f"Error processing goal {slug}: {e}")
                continue

        return result

    def _get_urgency_level(self, safebuf: int) -> str:
        """Determine urgency level based on safety buffer days"""
        if safebuf < 1:
            return "red"     # Emergency (today)
        elif safebuf < 2:
            return "yellow"  # Due tomorrow
        elif safebuf < 3:
            return "blue"    # Due in 2 days
        elif safebuf < 7:
            return "green"   # Due in 3-6 days
        else:
            return "gray"    # Due in 7+ days