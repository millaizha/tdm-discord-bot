import os
import json
import threading
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from flask import Flask
from dotenv import load_dotenv

from todomate import (
    fetch_todo_items_today,
    generate_todo_summary_today,
    generate_todo_summary_tomorrow,
    generate_todo_summary_week,
    generate_todo_summary_backlog
)

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
TASKS_CHANNEL_ID = int(os.getenv("TASKS_CHANNEL_ID", "0"))
CALLS_CHANNEL_ID = int(os.getenv("CALLS_CHANNEL_ID", "0"))
USERS = json.loads(os.getenv("USERS", "{}"))

REMINDER_INTERVALS = [120, 60, 30, 10, 5]

# Initialize Flask app
app = Flask(__name__)

@app.route('/')
def index():
    return "✅ TodoMate Discord Bot is running on Azure!"

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True  # ✅ Required to fetch and edit member nicknames
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}", flush=True)
    check_and_send_reminders.start()
    send_tomorrow_summary.start()
    send_backlog_summary.start()

# Background task to check reminders and send today's summary
@tasks.loop(minutes=1)
async def check_and_send_reminders():
    now = datetime.now(ZoneInfo("Asia/Manila"))
    send_times = [time(8, 0), time(12, 0), time(16, 0), time(20, 0)]

    # Send daily summaries at fixed times
    if any(now.hour == t.hour and now.minute == t.minute for t in send_times):
        summary = generate_todo_summary_today(USERS)
        channel = bot.get_channel(TASKS_CHANNEL_ID)
        if summary:
            await channel.send(summary)

    # Per-user reminders
    raw_data = fetch_todo_items_today(USERS)
    todos_by_user = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    user_lookup = {v["todomate"]: k for k, v in USERS.items() if "todomate" in v}

    for internal_id, todos in todos_by_user.items():
        discord_id = user_lookup.get(internal_id)
        if not discord_id:
            continue

        for todo in todos:
            remind_at_str = todo.get("remindAt")
            if not remind_at_str:
                continue

            try:
                remind_dt = datetime.strptime(remind_at_str, '%Y-%m-%d %I:%M:%S %p').replace(tzinfo=ZoneInfo("Asia/Manila"))
            except Exception as e:
                print(f"⚠️ Failed to parse remindAt: {remind_at_str} ({e})")
                continue

            delta_min = int((remind_dt - now).total_seconds() / 60)
            if delta_min in REMINDER_INTERVALS:
                try:
                    user = await bot.fetch_user(int(discord_id))
                    if delta_min >= 60:
                        label = f"{delta_min // 60} hour(s)"
                    else:
                        label = f"{delta_min} minutes"
                    await user.send(f"⏰ Reminder: **{todo['content']}** in {label}!")
                except Exception as e:
                    print(f"❌ Could not DM <@{discord_id}>: {e}")

# Task: Send tomorrow's todos at 10:30 PM
@tasks.loop(minutes=1)
async def send_tomorrow_summary():
    now = datetime.now(ZoneInfo("Asia/Manila"))
    if now.hour == 22 and now.minute == 30:
        summary = generate_todo_summary_tomorrow(USERS)
        channel = bot.get_channel(TASKS_CHANNEL_ID)
        if summary:
            await channel.send(f"🌙 Here's what everyone has tomorrow:\n{summary}")

# Task: Send backlog items at 6 AM
@tasks.loop(minutes=1)
async def send_backlog_summary():
    now = datetime.now(ZoneInfo("Asia/Manila"))
    if now.hour == 6 and now.minute == 0:
        summary = generate_todo_summary_backlog(USERS)
        channel = bot.get_channel(TASKS_CHANNEL_ID)
        if summary:
            await channel.send(f"📜 Here's the backlog of unfinished tasks:\n{summary}")

# Voice channel join/leave notification
@bot.event
async def on_voice_state_update(member, before, after):
    member_id_str = str(member.id)

    if member_id_str not in USERS:
        return

    try:
        channel = bot.get_channel(CALLS_CHANNEL_ID)
        if before.channel is None and after.channel is not None:
            if after.channel.id == CALLS_CHANNEL_ID and len(after.channel.members) == 1:
                for other_id in USERS:
                    if other_id != member_id_str:
                        await channel.send(f"📢 <@{other_id}>, <@{member_id_str}> just joined **{after.channel.name}**!")
        elif before.channel is not None and after.channel is None:
            if before.channel.id == CALLS_CHANNEL_ID:
                for other_id in USERS:
                    if other_id != member_id_str:
                        await channel.send(f"👋 <@{other_id}>, <@{member_id_str}> just left **{before.channel.name}**.")
    except Exception as e:
        print(f"❌ Voice event error for <@{member_id_str}>: {e}")

# Discord command: !today
@bot.command(name="today")
async def today(ctx):
    try:
        summary = generate_todo_summary_today(USERS)
        await ctx.send(summary if summary else "✅ No todos scheduled for today.")
    except Exception as e:
        await ctx.send("❌ An error occurred while fetching today's todos.")
        print("🚨 Error:", e, flush=True)

# Discord command: !tom
@bot.command(name="tom")
async def tomorrow(ctx):
    try:
        summary = generate_todo_summary_tomorrow(USERS)
        await ctx.send(summary if summary else "✅ No todos scheduled for tomorrow.")
    except Exception as e:
        await ctx.send("❌ An error occurred while fetching tomorrow's todos.")
        print("🚨 Error:", e, flush=True)

# Discord command: !week
@bot.command(name="week")
async def week(ctx):
    try:
        summary = generate_todo_summary_week(USERS)
        await ctx.send(summary if summary else "✅ No upcoming todos.")
    except Exception as e:
        await ctx.send("❌ An error occurred while fetching upcoming todos.")
        print("🚨 Error:", e, flush=True)

# Discord command: !backlog
@bot.command(name="backlog")
async def backlog(ctx):
    try:
        summary = generate_todo_summary_backlog(USERS)
        await ctx.send(summary if summary else "✅ No backlog items.")
    except Exception as e:
        await ctx.send("❌ An error occurred while fetching backlog items.")
        print("🚨 Error:", e, flush=True)

# Run Flask in separate thread
def run_flask():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

# Entry point
if __name__ == "__main__":
    print("🚀 Starting Flask and Discord bot...", flush=True)

    # Start Flask server
    threading.Thread(target=run_flask).start()

    # Run Discord bot
    bot.run(DISCORD_TOKEN)