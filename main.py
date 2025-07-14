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
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}", flush=True)
    print(f"🔧 Tasks Channel ID: {TASKS_CHANNEL_ID}", flush=True)
    print(f"🔧 Calls Channel ID: {CALLS_CHANNEL_ID}", flush=True)
    print(f"🔧 Users: {USERS}", flush=True)
    
    # Verify channels exist
    tasks_channel = bot.get_channel(TASKS_CHANNEL_ID)
    calls_channel = bot.get_channel(CALLS_CHANNEL_ID)
    
    if not tasks_channel:
        print(f"❌ Tasks channel with ID {TASKS_CHANNEL_ID} not found!", flush=True)
    else:
        print(f"✅ Tasks channel found: {tasks_channel.name}", flush=True)
    
    if not calls_channel:
        print(f"❌ Calls channel with ID {CALLS_CHANNEL_ID} not found!", flush=True)
    else:
        print(f"✅ Calls channel found: {calls_channel.name}", flush=True)
    
    # Start background tasks
    if not check_and_send_reminders.is_running():
        check_and_send_reminders.start()
    if not send_tomorrow_summary.is_running():
        send_tomorrow_summary.start()
    if not send_backlog_summary.is_running():
        send_backlog_summary.start()

# Background task to check reminders and send today's summary
@tasks.loop(minutes=1)
async def check_and_send_reminders():
    try:
        now = datetime.now(ZoneInfo("Asia/Manila"))
        send_times = [time(8, 0), time(12, 0), time(16, 0), time(20, 0)]

        # Send daily summaries at fixed times
        if any(now.hour == t.hour and now.minute == t.minute for t in send_times):
            print(f"📅 Sending daily summary at {now.strftime('%H:%M')}", flush=True)
            try:
                summary = generate_todo_summary_today(USERS)
                channel = bot.get_channel(TASKS_CHANNEL_ID)
                if channel and summary:
                    await channel.send(summary)
                    print(f"✅ Daily summary sent successfully", flush=True)
                elif not channel:
                    print(f"❌ Tasks channel not found for daily summary", flush=True)
                else:
                    print(f"ℹ️ No summary to send", flush=True)
            except Exception as e:
                print(f"❌ Error sending daily summary: {e}", flush=True)

        # Per-user reminders
        try:
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
                        print(f"⚠️ Failed to parse remindAt: {remind_at_str} ({e})", flush=True)
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
                            print(f"✅ Reminder sent to user {discord_id}", flush=True)
                        except Exception as e:
                            print(f"❌ Could not DM <@{discord_id}>: {e}", flush=True)
        except Exception as e:
            print(f"❌ Error processing reminders: {e}", flush=True)

    except Exception as e:
        print(f"❌ Critical error in check_and_send_reminders: {e}", flush=True)

# Task: Send tomorrow's todos at 10:30 PM
@tasks.loop(minutes=1)
async def send_tomorrow_summary():
    try:
        now = datetime.now(ZoneInfo("Asia/Manila"))
        if now.hour == 22 and now.minute == 30:
            print(f"🌙 Sending tomorrow's summary at {now.strftime('%H:%M')}", flush=True)
            try:
                summary = generate_todo_summary_tomorrow(USERS)
                channel = bot.get_channel(TASKS_CHANNEL_ID)
                if channel and summary:
                    await channel.send(f"🌙 Here's what everyone has tomorrow:\n{summary}")
                    print(f"✅ Tomorrow's summary sent successfully", flush=True)
                elif not channel:
                    print(f"❌ Tasks channel not found for tomorrow's summary", flush=True)
                else:
                    print(f"ℹ️ No tomorrow's summary to send", flush=True)
            except Exception as e:
                print(f"❌ Error sending tomorrow's summary: {e}", flush=True)
    except Exception as e:
        print(f"❌ Critical error in send_tomorrow_summary: {e}", flush=True)

# Task: Send backlog items at 6 AM
@tasks.loop(minutes=1)
async def send_backlog_summary():
    try:
        now = datetime.now(ZoneInfo("Asia/Manila"))
        if now.hour == 6 and now.minute == 0:
            print(f"📜 Sending backlog summary at {now.strftime('%H:%M')}", flush=True)
            try:
                summary = generate_todo_summary_backlog(USERS)
                channel = bot.get_channel(TASKS_CHANNEL_ID)
                if channel and summary:
                    await channel.send(f"📜 Here's the backlog of unfinished tasks:\n{summary}")
                    print(f"✅ Backlog summary sent successfully", flush=True)
                elif not channel:
                    print(f"❌ Tasks channel not found for backlog summary", flush=True)
                else:
                    print(f"ℹ️ No backlog summary to send", flush=True)
            except Exception as e:
                print(f"❌ Error sending backlog summary: {e}", flush=True)
    except Exception as e:
        print(f"❌ Critical error in send_backlog_summary: {e}", flush=True)

# Voice channel join/leave notification
@bot.event
async def on_voice_state_update(member, before, after):
    try:
        member_id_str = str(member.id)
        print(f"🎤 Voice state update for {member.display_name} (ID: {member_id_str})", flush=True)
        print(f"   Before: {before.channel.name if before.channel else 'None'}", flush=True)
        print(f"   After: {after.channel.name if after.channel else 'None'}", flush=True)

        if member_id_str not in USERS:
            print(f"   User {member_id_str} not in USERS config", flush=True)
            return

        channel = bot.get_channel(CALLS_CHANNEL_ID)
        if not channel:
            print(f"❌ Calls channel with ID {CALLS_CHANNEL_ID} not found!", flush=True)
            return

        # User joined a voice channel
        if before.channel is None and after.channel is not None:
            print(f"   User joined channel: {after.channel.name} (ID: {after.channel.id})", flush=True)
            print(f"   Channel members count: {len(after.channel.members)}", flush=True)
            
            # Check if this is the Lounge voice channel AND user is first to join
            if after.channel.id == 1346875171222454307 and len(after.channel.members) == 1:
                print(f"   First user in the Lounge voice channel, notifying others", flush=True)
                for other_id in USERS:
                    if other_id != member_id_str:
                        try:
                            await channel.send(f"📢 <@{other_id}>, <@{member_id_str}> just joined **{after.channel.name}**!")
                            print(f"   Notified user {other_id}", flush=True)
                        except Exception as e:
                            print(f"   Failed to notify user {other_id}: {e}", flush=True)
            elif after.channel.id == 1346875171222454307:
                print(f"   User joined Lounge but not first (members: {len(after.channel.members)})", flush=True)
            else:
                print(f"   User joined different voice channel: {after.channel.name} (ID: {after.channel.id})", flush=True)
        
        # User left a voice channel
        elif before.channel is not None and after.channel is None:
            print(f"   User left channel: {before.channel.name} (ID: {before.channel.id})", flush=True)
            
            if before.channel.id == 1346875171222454307:
                print(f"   User left the Lounge voice channel, notifying others", flush=True)
                for other_id in USERS:
                    if other_id != member_id_str:
                        try:
                            await channel.send(f"👋 <@{other_id}>, <@{member_id_str}> just left **{before.channel.name}**.")
                            print(f"   Notified user {other_id}", flush=True)
                        except Exception as e:
                            print(f"   Failed to notify user {other_id}: {e}", flush=True)
            else:
                print(f"   User left different voice channel: {before.channel.name} (ID: {before.channel.id})", flush=True)

    except Exception as e:
        print(f"❌ Voice event error for {member.display_name}: {e}", flush=True)

# Error handler for background tasks
@check_and_send_reminders.error
async def check_and_send_reminders_error(error):
    print(f"❌ Error in check_and_send_reminders task: {error}", flush=True)

@send_tomorrow_summary.error
async def send_tomorrow_summary_error(error):
    print(f"❌ Error in send_tomorrow_summary task: {error}", flush=True)

@send_backlog_summary.error
async def send_backlog_summary_error(error):
    print(f"❌ Error in send_backlog_summary task: {error}", flush=True)

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