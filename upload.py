import sys
import os
import requests
import time

def upload_file(file_path: str, url: str):
    """
    Uploads a file to a specified URL via an HTTP POST request.

    Args:
        file_path (str): The relative path to the file to upload.
        url (str): The destination URL.
    """
    # 1. Validate the input file path
    abs_file_path = os.path.abspath(file_path)
    if not os.path.isfile(abs_file_path):
        print(f"Error: The path '{file_path}' is not a valid file.")
        sys.exit(1)

    file_name = os.path.basename(abs_file_path)
    
    print(f"Attempting to upload '{file_name}' to '{url}'...")
    start_time = time.time()

    try:
        # 2. Open the file in binary read mode
        with open(abs_file_path, 'rb') as f:
            # 3. Prepare the multipart/form-data payload.
            # The key 'compressedFile' is what the server-side handler (e.g., multer)
            # will look for. This should match your server's configuration.
            files = {'compressedFile': (file_name, f)}
            
            # 4. Make the POST request
            response = requests.post(url, files=files, timeout=60) # 60-second timeout

            # 5. Check the server's response
            response.raise_for_status()  # This will raise an exception for 4xx or 5xx status codes

    except requests.exceptions.RequestException as e:
        print(f"\nAn error occurred during the upload: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        sys.exit(1)

    end_time = time.time()
    duration = end_time - start_time

    # 6. Report the results
    print("\nUpload successful!")
    print(f"  - Status Code: {response.status_code}")
    print(f"  - Time taken:  {duration:.2f} seconds")
    print("\nServer Response:")
    try:
        # Try to print formatted JSON, fall back to raw text if it fails
        print(response.json())
    except requests.exceptions.JSONDecodeError:
        print(response.text)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python upload.py <path_to_file> <url>")
        print("Example: python upload.py ./my_archive.tar.gz http://localhost:3000/api/upload")
        sys.exit(1)
    
    file_to_upload = sys.argv[1]
    target_url = sys.argv[2]
    upload_file(file_to_upload, target_url)
