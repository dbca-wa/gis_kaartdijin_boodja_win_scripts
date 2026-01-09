import sys
import os
import requests
import json
import shutil
from datetime import datetime


def print_with_timestamp(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}") 


def handle_exceptions(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.HTTPError as e:
            print_with_timestamp(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print_with_timestamp(f"An error occurred: {e}")
    return wrapper


@handle_exceptions
def fetch_file_list(api_url, username, password):
    # Fetch file list from the API
    print_with_timestamp(f"Fetching file list from API: {api_url}")
    response = requests.get(api_url, auth=(username, password))
    response.raise_for_status()
    files = response.json()  # Get file information as JSON
    print_with_timestamp("File list fetched successfully.")
    return files

    ### Example usage
    # api_url = "https://kaartijin-boodja-server/api/publish/cddp-contents/"
    # fetch_file_list(api_url)


@handle_exceptions
def download_file_and_get_path(api_url, username, password, file_path, download_dir="."):
    """
    Downloads a file from the API via streaming and saves it locally.
    Returns the path to the saved file on success.
    """
    # Note: Using os.path.join for a URL is not ideal, but we'll keep it for consistency with the original code.
    # A better approach is url = api_url.rstrip('/') + '/retrieve-file'
    endpoint_url = os.path.join(api_url, 'retrieve-file')
    print_with_timestamp(f"Downloading file from: {endpoint_url} with filepath: {file_path}")

    # Use stream=True to enable streaming mode for the response.
    response = requests.get(endpoint_url, auth=(username, password), params={'filepath': file_path}, stream=True)
    response.raise_for_status()

    # Determine the destination file path.
    # local_filename = os.path.join(download_dir, os.path.basename(file_path))
    local_filename = os.path.join(download_dir, file_path)
    print_with_timestamp(f"Saving file to: {local_filename}")

    # Write the file to disk chunk by chunk.
    try:
        with open(local_filename, 'wb') as f:
            # shutil.copyfileobj provides an efficient way to write the stream to a file.
            shutil.copyfileobj(response.raw, f)
            # Alternatively, you can iterate manually:
            # for chunk in response.iter_content(chunk_size=8192): 
            #     f.write(chunk)
        
        print_with_timestamp("File downloaded successfully.")
        # Return the path to the saved file
        return local_filename
    except Exception as e:
        # If an error occurs, clean up the partially downloaded file.
        if os.path.exists(local_filename):
            os.remove(local_filename)
        print_with_timestamp(f"Failed to write file: {e}")
        raise # Re-raise the exception to signal failure.


@handle_exceptions
def delete_file_remotely(api_url, username, password, file_path):
    # Destroy the file using the API
    api_url = api_url.rstrip('/') + '/delete-file/'
    response = requests.delete(api_url, auth=(username, password), params={'filepath': file_path})
    response.raise_for_status()
    
    print_with_timestamp(f"File [{file_path}] deleted successfully")

    ### Example usage
    # api_url = "https://kaartijin-boodja-server/api/publish/cddp-contents/destroy-file/"
    # file_path = "path/to/file"
    # delete_file(api_url, file_path)


def read_config_json(filename='config.ini'):
    """
    Read JSON data directly from a config.ini file located in the same folder as the script.
    Args: filename (str): Name of the config file. Default is 'config.ini'.
    Returns: dict: JSON data read from the config file or environment variables.
    """
    config_path = os.path.join(os.path.dirname(__file__), filename)

    if os.path.exists(config_path):
        print_with_timestamp(f"Reading JSON data from config file: {config_path}")
        with open(config_path, 'r') as file:
            json_data = json.load(file)
        print_with_timestamp("JSON data read successfully.")
    else:
        raise EnvironmentError(f"config.ini file not found")

    return json_data


def create_folder(folder_path):
    """
    Create a folder at the specified path if it does not exist.
    Args: folder_path (str): Path of the folder to be created.
    """
    # Check if the folder already exists
    if os.path.exists(folder_path):
        print_with_timestamp(f"Folder '{folder_path}' already exists.")
    else:
        # Create the folder and its parent directories if they don't exist
        try:
            os.makedirs(folder_path)
            print_with_timestamp(f"Folder '{folder_path}' created successfully.")
        except OSError as e:
            print_with_timestamp(f"Failed to create folder '{folder_path}': {e}")


# Start this script
print_with_timestamp('Starting the script...')

# Open config file
if len(sys.argv) > 1:
    config_file_path = sys.argv[1]
else:
    config_file_path = 'config/config.ini'
config_data = read_config_json(config_file_path)

# Create local distination folder
create_folder(config_data['LOCAL_DESTINATION_FOLDER'])

# Fetch file info
response = fetch_file_list(config_data['FILE_SYNC_ENDPOINT_URL'], config_data['KB_USERNAME'], config_data['KB_PASSWORD'])
print_with_timestamp(response)
total_files = response['count']

if not total_files:
    print_with_timestamp('No files found.')
    sys.exit(0)

# Print total number of files
print_with_timestamp(f'Total number of files: {total_files}')

count = 0
for file_info in response['results']:
    count += 1
    print_with_timestamp(f"--- File#{count} (out of {total_files}) files ---")

    # Download file and get local path
    local_file_path = download_file_and_get_path(config_data['FILE_SYNC_ENDPOINT_URL'], config_data['KB_USERNAME'], config_data['KB_PASSWORD'], file_info['filepath'], config_data['LOCAL_DESTINATION_FOLDER'])
    if local_file_path:
        # Destroy file from the server
        delete_file_remotely(config_data['FILE_SYNC_ENDPOINT_URL'], config_data['KB_USERNAME'], config_data['KB_PASSWORD'], file_info['filepath'])
