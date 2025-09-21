import sys
import os
import requests
import time
import json
from urllib.parse import urljoin

def login(base_url: str, username: str, password: str) -> str | None:
    """Attempts to log in and returns a JWT token if successful."""
    login_url = urljoin(base_url, "/api/auth/login")
    print(f"Attempting to log in as '{username}'...")
    try:
        response = requests.post(login_url, json={'username': username, 'password': password}, timeout=10)
        if response.status_code == 200:
            token = response.json().get('jwt')
            if token:
                print("Login successful.")
                return token
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error during login request: {e}")
        return None

def register(base_url: str, username: str, password: str) -> str | None:
    """Attempts to register a new user if login fails."""
    register_url = urljoin(base_url, "/api/auth/register")
    print(f"Login failed. Attempting to register new user '{username}'...")
    try:
        response = requests.post(register_url, json={'username': username, 'password': password}, timeout=10)
        if response.status_code == 201:
            data = response.json()
            token = data.get('jwt')
            words = data.get('words')
            print("Registration successful.")
            if words:
                print("\nIMPORTANT: Please save your secret recovery words.")
                print("-----------------------------------")
                print(" ".join(words))
                print("-----------------------------------\n")
            return token
        else:
            print(f"Registration failed with status {response.status_code}: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error during registration request: {e}")
        return None

def restore_system(system_id: str, base_url: str, token: str):
    """
    Restores a tainted agent system using a JWT for authentication.

    Args:
        system_id: The ID of the agent system to restore.
        base_url: The base URL of the server.
        token: The JWT for authentication.
    """
    restore_url = urljoin(base_url, f"/api/systems/restore/{system_id}")
    
    print(f"\nAuthenticated. Attempting to restore system ID '{system_id}' at '{restore_url}'...")
    start_time = time.time()

    try:
        headers = {'Authorization': f'Bearer {token}'}
        
        # Restore is a POST request as it changes the state of the resource.
        response = requests.post(restore_url, headers=headers, timeout=60)
        
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred during the restore operation: {e}")
        if e.response is not None:
            print(f"Server response ({e.response.status_code}): {e.response.text}")
        sys.exit(1)

    end_time = time.time()
    duration = end_time - start_time

    print("\nRestore operation successful!")
    print(f"  - Status Code: {response.status_code}")
    print(f"  - Time taken:  {duration:.2f} seconds")
    print("\nServer Response:")
    try:
        print(json.dumps(response.json(), indent=2))
    except json.JSONDecodeError:
        print(response.text)

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python restore.py <system_id> <base_url> <username> <password>")
        print("Example: python restore.py 12345 http://localhost:8080 my-user my-pass")
        sys.exit(1)
    
    system_id_to_restore, base_url, username, password = sys.argv[1:5]

    auth_token = login(base_url, username, password)
    if not auth_token:
        auth_token = register(base_url, username, password)
        if not auth_token:
            print("\nRegistration failed. Could not authenticate. Aborting.")
            sys.exit(1)
            
    restore_system(system_id_to_restore, base_url, auth_token)