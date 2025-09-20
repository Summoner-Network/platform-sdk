import sys
import os
import requests
import time
import json
from urllib.parse import urljoin

def login(base_url: str, username: str, password: str) -> str | None:
    """
    Attempts to log in.

    Returns:
        The JWT token string if successful, otherwise None.
    """
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
    """
    Attempts to register a new user.

    Returns:
        The JWT token string if successful, otherwise None.
    """
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

def upload_file(file_path: str, base_url: str, token: str):
    """
    Uploads a file using a JWT for authentication.

    Args:
        file_path: The path to the .tar.gz file to upload.
        base_url: The base URL of the server.
        token: The JWT for authentication.
    """
    # CORRECTED URL: The endpoint for deploying agents is /api/agent/deploy
    deploy_url = urljoin(base_url, "/api/systems/deploy")
    
    abs_file_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_file_path):
        print(f"Error: The path '{file_path}' is not a valid file.")
        sys.exit(1)

    file_name = os.path.basename(abs_file_path)
    
    print(f"\nAuthenticated. Attempting to upload '{file_name}' to '{deploy_url}'...")
    start_time = time.time()

    try:
        with open(abs_file_path, 'rb') as f:
            files = {'agentPackage': (file_name, f)}
            headers = {'Authorization': f'Bearer {token}'}
            
            response = requests.post(deploy_url, files=files, headers=headers, timeout=60)
            
            response.raise_for_status()

    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred during the upload: {e}")
        if e.response is not None:
            print(f"Server response ({e.response.status_code}): {e.response.text}")
        sys.exit(1)

    end_time = time.time()
    duration = end_time - start_time

    print("\nUpload successful!")
    print(f"  - Status Code: {response.status_code}")
    print(f"  - Time taken:  {duration:.2f} seconds")
    print("\nServer Response:")
    try:
        print(json.dumps(response.json(), indent=2))
    except requests.exceptions.JSONDecodeError:
        print(response.text)

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python upload.py <path_to_file> <base_url> <username> <password>")
        print("Example: python upload.py ./src.tar.gz http://localhost:8080 my-user my-pass")
        sys.exit(1)
    
    file_to_upload, base_url, username, password = sys.argv[1:5]

    # 1. Try to log in first to get a token.
    auth_token = login(base_url, username, password)

    # 2. If login fails (no token), try to register.
    if not auth_token:
        auth_token = register(base_url, username, password)
        # If registration also fails, we can't proceed.
        if not auth_token:
            print("\nRegistration failed. Could not authenticate. Aborting.")
            sys.exit(1)
        
        # NOTE: Registration provides a token, so no need to log in again immediately.

    # 3. By this point, we should have a token. Proceed with the file upload.
    upload_file(file_to_upload, base_url, auth_token)

