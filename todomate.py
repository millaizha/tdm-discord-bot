import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

# Function to format timestamps in milliseconds to a readable string
def format_timestamp(ms):
    if ms is None:
        return None
    ph_time = datetime.fromtimestamp(ms / 1000, tz=ZoneInfo("Asia/Manila"))
    return ph_time.strftime('%Y-%m-%d %I:%M:%S %p')

# Function to get the start and end timestamps for today in milliseconds
def get_now_ms():
    start = datetime.now(ZoneInfo("Asia/Manila")).replace(hour=0, minute=0, second=0, microsecond=0)
    end = datetime.now(ZoneInfo("Asia/Manila")).replace(hour=23, minute=59, second=59, microsecond=999000)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)

# Function to get the next 7 days' range in milliseconds
def get_week_ms():
    start = datetime.now(ZoneInfo("Asia/Manila")).replace(hour=0, minute=0, second=0, microsecond=0)
    end = (start + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999000)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)

load_dotenv() 

# Authenticate via Firebase
firebase_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=AIzaSyCtSjt1LBEXmQnZdjD8DOPXBc5I1acm0Ew"

def get_id_token():
    auth_payload = {
        "email": os.getenv("EMAIL"),
        "password": os.getenv("PASSWORD"),
        "returnSecureToken": True
    }
    auth_res = requests.post(firebase_url, json=auth_payload)
    auth_res.raise_for_status()
    id_token = auth_res.json()["idToken"]

    # API endpoint and headers
    api_url = "https://loadfeeditems-2lresvldza-uc.a.run.app/"
    headers = {
        "Authorization": f"Bearer {id_token}",
        "Content-Type": "application/json",
        "Origin": "https://www.todomate.net",
        "Referer": "https://www.todomate.net/",
        "User-Agent": "Mozilla/5.0"
    }

    return api_url, headers

# Function to fetch today's todo items
def fetch_todo_items_today(users):
    start_time, end_time = get_now_ms()
    all_results = {}
    api_url, headers = get_id_token()

    for label, user_id in users.items():
        data_payload = {
            "data": {
                "feedModelId": user_id,
                "feedModelType": "user",
                "startDate": start_time,
                "endDate": end_time
            }
        }

        res = requests.post(api_url, json=data_payload, headers=headers)
        res.raise_for_status()

        todo_items = res.json()["result"]["result"]["todoItems"]
        filtered = [
            {
                "content": item.get("content"),
                "date": format_timestamp(item.get("date")),
                "remindAt": format_timestamp(item.get("remindAt"))
            }
            for item in todo_items if not item.get("isDone", False)
        ]

        all_results[user_id] = filtered

    return json.dumps(all_results, indent=2, ensure_ascii=False)

# Function to format today's summary
def generate_todo_summary_today(users_dict):
    raw = fetch_todo_items_today(users_dict)
    todos_by_user = json.loads(raw) if isinstance(raw, str) else raw
    user_id_lookup = {v: k for k, v in users_dict.items()}
    response = ""

    for internal_id, todos in todos_by_user.items():
        discord_id = user_id_lookup.get(internal_id)
        if not discord_id:
            continue

        if isinstance(todos, dict) and "error" in todos:
            response += f"<@{discord_id}> ⚠️ Error: {todos['error']}\n"
            continue

        if not todos:
            continue

        response += f"\n📌 Todos for <@{discord_id}>:\n"
        for todo in todos:
            content = todo.get("content", "No content")
            remind_at = todo.get("remindAt")
            if remind_at:
                dt = datetime.strptime(remind_at, '%Y-%m-%d %I:%M:%S %p')
                time_part = dt.strftime('%I:%M %p').lstrip('0') 
                response += f"• **{content}** at {time_part}\n"
            else:
                response += f"• **{content}**\n"
        response += "\n"

    return response

# Function to fetch todo items for the next 7 days
def fetch_todo_items_week(users):
    start_time, end_time = get_week_ms()
    all_results = {}
    api_url, headers = get_id_token()

    for label, user_id in users.items():
        data_payload = {
            "data": {
                "feedModelId": user_id,
                "feedModelType": "user",
                "startDate": start_time,
                "endDate": end_time
            }
        }

        res = requests.post(api_url, json=data_payload, headers=headers)
        res.raise_for_status()

        todo_items = res.json()["result"]["result"]["todoItems"]
        filtered = [
            {
                "content": item.get("content"),
                "date": format_timestamp(item.get("date")),
                "remindAt": format_timestamp(item.get("remindAt"))
            }
            for item in todo_items if not item.get("isDone", False)
        ]

        all_results[user_id] = filtered

    return json.dumps(all_results, indent=2, ensure_ascii=False)

# Function to format weekly summary grouped by date
def generate_todo_summary_week(users_dict):
    raw = fetch_todo_items_week(users_dict)
    todos_by_user = json.loads(raw) if isinstance(raw, str) else raw
    user_id_lookup = {v: k for k, v in users_dict.items()}
    todos_by_date = defaultdict(lambda: defaultdict(list))

    for internal_id, todos in todos_by_user.items():
        discord_id = user_id_lookup.get(internal_id)
        if not discord_id:
            continue

        if isinstance(todos, dict) and "error" in todos:
            todos_by_date["Errors"][discord_id].append(f"⚠️ Error: {todos['error']}")
            continue

        for todo in todos:
            date_key = todo.get("date", "Unknown Date").split()[0] 
            content = todo.get("content", "No content")
            remind_at = todo.get("remindAt")
            todo_str = f"• **{content}**"
            if remind_at:
                dt = datetime.strptime(remind_at, '%Y-%m-%d %I:%M:%S %p')
                time_part = dt.strftime('%I:%M %p').lstrip('0') 
                todo_str += f" at {time_part}"
            todos_by_date[date_key][discord_id].append(todo_str)

    response = ""
    for date in sorted(todos_by_date.keys()):
        try:
            formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%b %d %Y (%A)")
        except ValueError:
            formatted_date = date 
        response += f"📅 **{formatted_date}**\n"
        
        for user_id, todos in todos_by_date[date].items():
            response += f"<@{user_id}>:\n"
            for todo in todos:
                response += f"{todo}\n"
            response += "\n"
        response += "\n"

    return response or "✅ No upcoming todos in the next 7 days."