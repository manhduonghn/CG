import os
import re
import json
import http.client
from src import ids_pattern, CACHE_FILE
from src.cloudflare import get_lists, get_rules, get_list_items

def load_cache(workflow_status=None):
def load_cache(workflow_status=None):
    try:
        if is_running_in_github_actions():
            if workflow_status is None:
                workflow_status = get_latest_workflow_status()

            print(f"Workflow status: {workflow_status}")
            
            if workflow_status == 'success':
                if os.path.exists(CACHE_FILE):
                    print(f"Cache file {CACHE_FILE} exists, loading...")
                    with open(CACHE_FILE, 'r') as file:
                        return json.load(file)
                else:
                    print(f"Cache file {CACHE_FILE} does not exist.")
            else:
                print(f"Workflow status is not 'success', deleting cache.")
                delete_cache()
        elif os.path.exists(CACHE_FILE):
            print(f"Running outside of GitHub Actions, cache file {CACHE_FILE} exists, loading...")
            with open(CACHE_FILE, 'r') as file:
                return json.load(file)
        else:
            print(f"Cache file {CACHE_FILE} does not exist.")
    except json.JSONDecodeError:
        print(f"Error decoding cache file {CACHE_FILE}. Returning empty cache.")
        return {"lists": [], "rules": [], "mapping": {}}
    
    print("Returning empty cache.")
    return {"lists": [], "rules": [], "mapping": {}}
    

def save_cache(cache):
    with open(CACHE_FILE, 'w') as file:
        json.dump(cache, file)

def get_current_lists(cache, list_name):
    if cache["lists"]:
        return cache["lists"]
    current_lists = get_lists(list_name)
    cache["lists"] = current_lists
    save_cache(cache)
    return current_lists

def get_current_rules(cache, rule_name):
    if cache["rules"]:
        return cache["rules"]
    current_rules = get_rules(rule_name)
    cache["rules"] = current_rules
    save_cache(cache)
    return current_rules

def get_list_items_cached(cache, list_id):
    if list_id in cache["mapping"]:
        return cache["mapping"][list_id]
    items = get_list_items(list_id)
    cache["mapping"][list_id] = items
    save_cache(cache)
    return items

def split_domain_list(domains, chunk_size):
    for i in range(0, len(domains), chunk_size):
        yield domains[i:i + chunk_size]

def safe_sort_key(list_item):
    match = re.search(r'\d+', list_item["name"])
    return int(match.group()) if match else float('inf')

def extract_list_ids(rule):
    if not rule or not rule.get('traffic'):
        return set()
    return set(ids_pattern.findall(rule['traffic']))

def delete_cache():
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')
    
    BASE_URL = f"api.github.com"
    CACHE_URL = f"/repos/{GITHUB_REPOSITORY}/actions/caches"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Python http.client"
    }

    conn = http.client.HTTPSConnection(BASE_URL)
    conn.request("GET", CACHE_URL, headers=headers)
    response = conn.getresponse()
    data = response.read()
    caches = json.loads(data).get('actions_caches', [])
    caches_to_delete = [cache['id'] for cache in caches]
        
    for cache_id in caches_to_delete:
        delete_url = f"{CACHE_URL}/{cache_id}"
        conn.request("DELETE", delete_url, headers=headers)
        delete_response = conn.getresponse()
        delete_response.read()
        
    conn.close()

def get_latest_workflow_status():
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')
    
    BASE_URL = "api.github.com"
    WORKFLOW_RUNS_URL = f"/repos/{GITHUB_REPOSITORY}/actions/runs?per_page=5"  # Fetch more runs to ensure we get a completed one
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Python http.client"
    }

    # Create a connection to fetch the workflow runs
    conn = http.client.HTTPSConnection(BASE_URL)
    conn.request("GET", WORKFLOW_RUNS_URL, headers=headers)
    response = conn.getresponse()
    
    if response.status != 200:
        print("Error fetching workflow runs.")
        conn.close()
        return None
    
    data = response.read()
    runs = json.loads(data).get('workflow_runs', [])
    conn.close()  # Close the connection after reading the response

    # Filter only completed workflows
    completed_runs = [run for run in runs if run['status'] == 'completed']
    
    # Process each completed run
    if completed_runs:
        for run in completed_runs:
            run_id = run['id']
            conclusion = run['conclusion']  # 'success', 'failure', etc.
            print(f"Workflow {run_id} has status {conclusion}.")

            # If the conclusion is 'success', proceed with deletion
            if conclusion == 'success':
                # Create a new connection for each delete request
                conn = http.client.HTTPSConnection(BASE_URL)
                delete_url = f"/repos/{GITHUB_REPOSITORY}/actions/runs/{run_id}"
                conn.request("DELETE", delete_url, headers=headers)
                delete_response = conn.getresponse()
                
                # Check if deletion was successful
                if delete_response.status == 204:
                    print(f"Deleted workflow run {run_id} successfully.")
                else:
                    print(f"Failed to delete workflow run {run_id}. Status: {delete_response.status}")
                    
                conn.close()  # Close the connection after the DELETE request

    return None

def is_running_in_github_actions():
    github_actions = os.getenv('GITHUB_ACTIONS')
    return github_actions == 'true'
