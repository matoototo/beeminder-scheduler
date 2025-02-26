"""
Beeminder API Client
A simple wrapper for the Beeminder API
"""

import requests
from typing import Dict, List, Optional

class BeeminderAPI:
    """Simple client for interacting with the Beeminder API"""

    BASE_URL = "https://www.beeminder.com/api/v1"

    def __init__(self, username: str, auth_token: str):
        """Initialize with Beeminder credentials"""
        self.username = username
        self.auth_token = auth_token

    def get_user(self) -> Dict:
        """Get information about the current user"""
        url = f"{self.BASE_URL}/users/{self.username}.json"
        params = {'auth_token': self.auth_token}

        response = requests.get(url, params=params)
        response.raise_for_status()

        return response.json()

    def get_goals(self, include_archived: bool = False) -> List[Dict]:
        """Fetch all goals from Beeminder API"""
        endpoint = "goals/archived.json" if include_archived else "goals.json"
        url = f"{self.BASE_URL}/users/{self.username}/{endpoint}"
        params = {'auth_token': self.auth_token}

        response = requests.get(url, params=params)
        response.raise_for_status()

        return response.json()

    def get_goal(self, slug: str, include_datapoints: bool = False) -> Dict:
        """Get detailed information for a specific goal"""
        url = f"{self.BASE_URL}/users/{self.username}/goals/{slug}.json"
        params = {
            'auth_token': self.auth_token,
            'datapoints': include_datapoints
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        return response.json()

    def get_datapoints(self, goal_slug: str) -> List[Dict]:
        """Get all datapoints for a specific goal"""
        url = f"{self.BASE_URL}/users/{self.username}/goals/{goal_slug}/datapoints.json"
        params = {'auth_token': self.auth_token}

        response = requests.get(url, params=params)
        response.raise_for_status()

        return response.json()

    def create_datapoint(self, goal_slug: str, value: float,
                         timestamp: Optional[int] = None,
                         comment: str = "",
                         request_id: Optional[str] = None) -> Dict:
        """Submit a new datapoint to a goal"""
        url = f"{self.BASE_URL}/users/{self.username}/goals/{goal_slug}/datapoints.json"

        data = {
            'auth_token': self.auth_token,
            'value': value,
            'comment': comment
        }

        if timestamp:
            data['timestamp'] = timestamp

        if request_id:
            data['requestid'] = request_id

        response = requests.post(url, data=data)
        response.raise_for_status()

        return response.json()

    def refresh_goal(self, goal_slug: str) -> bool:
        """Force a refresh of a goal's graph and data"""
        url = f"{self.BASE_URL}/users/{self.username}/goals/{goal_slug}/refresh_graph.json"
        params = {'auth_token': self.auth_token}

        response = requests.get(url, params=params)
        response.raise_for_status()

        return response.json()

    def test_auth(self) -> bool:
        """Test if authentication credentials are valid"""
        try:
            self.get_goals()
            return True
        except:
            return False
