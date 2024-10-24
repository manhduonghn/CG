import os
import json
import http.client
from src import ids_pattern, CACHE_FILE
from src.cloudflare import get_lists, get_rules, get_list_items


def load_cache():
    try:
        if is_running_in_github_actions():
            # Kiểm tra trạng thái workflow gần nhất
            workflow_status, completed_run_ids = get_latest_workflow_status()
            
            if workflow_status == 'success':  # Nếu thành công, sử dụng cache
                if os.path.exists(CACHE_FILE):
                    with open(CACHE_FILE, 'r') as file:
                        return json.load(file)

            # Xóa các workflow run đã hoàn thành
            delete_completed_workflows(completed_run_ids)

        elif os.path.exists(CACHE_FILE):  # Nếu không chạy trên GitHub Actions
            with open(CACHE_FILE, 'r') as file:
                return json.load(file)
    except json.JSONDecodeError:
        return {"lists": [], "rules": [], "mapping": {}}
    
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


def delete_completed_workflows(completed_run_ids):
    GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
    GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY')
    
    BASE_URL = "api.github.com"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Python http.client"
    }

    conn = http.client.HTTPSConnection(BASE_URL)

    # Xóa các workflow run hoàn thành nếu có
    if completed_run_ids:
        for run_id in completed_run_ids:
            delete_url = f"/repos/{GITHUB_REPOSITORY}/actions/runs/{run_id}"
            conn.request("DELETE", delete_url, headers=headers)
            delete_response = conn.getresponse()
            if delete_response.status == 204:
                print(f"Successfully deleted workflow run with ID {run_id}.")
            else:
                print(f"Failed to delete workflow run with ID {run_id}. Status: {delete_response.status}")
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

    conn = http.client.HTTPSConnection(BASE_URL)
    conn.request("GET", WORKFLOW_RUNS_URL, headers=headers)
    response = conn.getresponse()
    
    if response.status != 200:
        return None, None
    
    data = response.read()
    
    runs = json.loads(data).get('workflow_runs', [])
    
    # Lọc các workflows hoàn thành
    completed_runs = [run for run in runs if run['status'] == 'completed']
    
    if completed_runs:
        latest_run = completed_runs[0]
        completed_run_ids = [run['id'] for run in completed_runs]
        return latest_run['conclusion'], completed_run_ids  # Trả về trạng thái và danh sách ID của các workflow đã hoàn thành
    
    return None, []


def is_running_in_github_actions():
    github_actions = os.getenv('GITHUB_ACTIONS')
    return github_actions == 'true'
