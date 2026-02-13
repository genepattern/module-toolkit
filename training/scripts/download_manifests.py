import requests
import os
import re
import argparse
import sys


def save_genepattern_manifests(token):
    # --- Configuration ---
    tasks_url = "http://cloud.genepattern.org/gp/rest/v1/tasks/all.json"
    base_api_url = "http://cloud.genepattern.org/gp/rest/v1/tasks"
    output_dir = "manifests"

    # --- Setup Headers ---
    # The Authorization header is required for all requests
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    # --- Setup Output Directory ---
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created directory: {output_dir}")

    print(f"Fetching task list from: {tasks_url}...")

    try:
        # 1. Load the JSON blob (Passing headers)
        response = requests.get(tasks_url, headers=headers)

        # specific check for Auth errors
        if response.status_code in [401, 403]:
            print("Error: Authentication failed. Please check your token.")
            sys.exit(1)

        response.raise_for_status()

        data = response.json()

        # 2. Access the 'all_modules' list specifically
        if 'all_modules' not in data:
            print("Error: JSON response does not contain 'all_modules' key.")
            return

        modules = data['all_modules']
        print(f"Found {len(modules)} modules. Starting download...")

        # 3. Iterate through all modules
        for module in modules:
            task_name = module.get('name')
            lsid = module.get('lsid')

            if not task_name or not lsid:
                print(f"Skipping module with missing data: {module}")
                continue

            # 4. Retrieve the manifest file via the API
            manifest_url = f"{base_api_url}/{lsid}/manifest"

            try:
                # Pass headers here as well for the manifest download
                manifest_response = requests.get(manifest_url, headers=headers)

                if manifest_response.status_code == 200:
                    # Sanitize filename
                    safe_filename = re.sub(r'[\\/*?:"<>|]', "_", task_name)
                    file_path = os.path.join(output_dir, f"{safe_filename}.properties")

                    # 5. Save manifest
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(manifest_response.text)

                    print(f"Saved: {safe_filename}.properties")
                elif manifest_response.status_code in [401, 403]:
                    print(f"Auth Error fetching {task_name} (Token might have expired)")
                else:
                    print(f"Failed to fetch manifest for {task_name} (Status: {manifest_response.status_code})")

            except requests.exceptions.RequestException as e:
                print(f"Error fetching manifest for {task_name}: {e}")

    except requests.exceptions.RequestException as e:
        print(f"Critical Error: Could not fetch the main task list. {e}")
    except ValueError as e:
        print(f"Critical Error: Response was not valid JSON. {e}")


if __name__ == "__main__":
    # Initialize Argument Parser
    parser = argparse.ArgumentParser(description="Download GenePattern module manifests.")

    # Add token argument
    parser.add_argument(
        "--token",
        required=True,
        help="Bearer token for GenePattern API authentication"
    )

    args = parser.parse_args()

    # Run the main function with the provided token
    save_genepattern_manifests(args.token)
