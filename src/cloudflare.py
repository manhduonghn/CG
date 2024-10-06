import os
import requests
from typing import List
from requests import retry, rate_limited_request


CF_API_TOKEN = os.environ["CF_API_TOKEN"]
CF_IDENTIFIER = os.environ["CF_IDENTIFIER"]

if not CF_API_TOKEN or not CF_IDENTIFIER:
    raise Exception("Missing Cloudflare credentials")

session = requests.session()
session.headers.update({"Authorization": f"Bearer {CF_API_TOKEN}"})


def get_lists(name_prefix: str):
    response = session.get(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/lists",
    )

    lists = response.json().get("result", [])
    return [lst for lst in lists if lst["name"].startswith(name_prefix)]


@rate_limited_request
@retry
def create_list(name: str, domains: List[str]):
    response = session.post(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/lists",
        json_data={
            "name": name,
            "description": "Created by script.",
            "type": "DOMAIN",
            "items": [{"value": domain} for domain in domains],
        },
    )

    return response.json()["result"]


@rate_limited_request
@retry
def delete_list(list_id: str):
    response = session.delete(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/lists/{list_id}",
    )
    return response.json()["result"]


def get_rules(name_prefix: str):
    response = session.get(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/rules",
    )
    rules = response.json().get("result", [])
    
    return [rule for rule in rules if rule["name"].startswith(name_prefix)]


def create_rule(name: str, list_ids: List[str]):
    response = session.post(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/rules",
        json_data={
            "name": name,
            "description": "Created by script.",
            "action": "block",
            "enabled": True,
            "filters": ["dns"],
            "traffic": " or ".join([f"any(dns.domains[*] in ${list_id})" for list_id in list_ids]),
            "rule_settings": {
                "block_page_enabled": False,
            },
        },
    )

    return response.json()["result"]


def update_rule(name: str, policy_id: str, list_ids: List[str]):
    response = session.put(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/rules/{policy_id}",
        json_data={
            "name": name,
            "action": "block",
            "enabled": True,
            "traffic": " or ".join([f"any(dns.domains[*] in ${list_id})" for list_id in list_ids]),
        },
    )

    return response.json()["result"]


def delete_rule(policy_id: str):
    response = session.delete(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/rules/{policy_id}"
    )

    return response.json()["result"]


def get_list_items(list_id: str):
    response = session.get(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/lists/{list_id}/items?limit=1000"
    )

    items = response.json()["result"]
    return [item["value"] for item in items]


@rate_limited_request
@retry
def update_list(list_id: str, remove_items: List[str], append_items: List[str]):
    response = session.patch(
        f"https://api.cloudflare.com/client/v4/accounts/{CF_IDENTIFIER}/gateway/lists/{list_id}",
        json_data={
            "remove": remove_items,
            "append": [{"value": item} for item in append_items],
        },
    )

    return response.json()["result"]
