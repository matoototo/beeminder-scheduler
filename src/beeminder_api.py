"""
Beeminder API Client
A simple wrapper for the Beeminder API
"""

import requests
from typing import Dict, List, Optional

class BeeminderAPI:
    BASE_URL = "https://www.beeminder.com/api/v1"

    def __init__(self, username: str, auth_token: str):
        self.username = username
        self.auth_token = auth_token

    def get_goals(self) -> List[Dict]:
        url = f"{self.BASE_URL}/users/{self.username}/goals.json"
        params = {'auth_token': self.auth_token}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_goal(self, slug: str) -> Dict:
        url = f"{self.BASE_URL}/users/{self.username}/goals/{slug}.json"
        params = {'auth_token': self.auth_token}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def test_auth(self) -> bool:
        try:
            self.get_goals()
            return True
        except:
            return False
