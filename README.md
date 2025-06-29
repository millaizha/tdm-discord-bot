# 📝 Discord Todo Mate Reminder Bot

This project is a Discord bot that sends todo reminders to a channel at scheduled times. It integrates with the [Todo Mate](https://www.todomate.net) API and supports multiple users.
It also notifies other members if a member is in a voice call

---

## 🚀 Features

- Sends reminders 5 times a day (8 AM, 12 PM, 4 PM, 8 PM, and 10:30 PM Manila time)
- Sends personal DMs for upcoming todos at 2 hours, 1 hour, 30 minutes, 10 minutes, and 5 minutes before their scheduled time
- Allows manual fetching of today, tommorow, or next 7 days' todos via a `!today`, `!tom`, or `!week` command
- Can also fetch unfinished tasks from the past week via `!backlog` command
- Notifies other members if a member is in a call
- Integrates with the Todo Mate API

> 🔒 **Note**: The bot can only fetch todo lists of users that are **visible to the authenticated Todo Mate account**. 
---

## 🛠️ Requirements

- Python 3.9+
- A Todo Mate account and user IDs (You must create another account that follows the users to fetch the todo lists)
- A Discord Bot Token
- Required Python packages (`requirements.txt`):

```txt
discord.py
python-dotenv
requests
schedule
flask
````

---

## 🧪 Local Setup

1. **Clone the repository**:

   ```bash
   git clone https://github.com/millaizha/tdm-discord-bot
   cd tdm-discord-bot
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Create a `.env` file** in the project root:

   ```env
   DISCORD_TOKEN=your_discord_bot_token
   TASKS_CHANNEL_ID=your_channel_id_as_integer_to_send_todo
   CALLS_CHANNEL_ID=your_channel_id_as_integer_to_send_call_notifs
   EMAIL=your_todomate_email
   PASSWORD=your_todomate_password
   USERS={"discord_user_id_1": {"todomate":"todomate_user_id_1"}, "discord_user_id_2": {"todomate":"todomate_user_id_2"}}
   ```

   > 📌 `USERS` must be a JSON string where the keys are **Discord user IDs** and the values are **Todo Mate user IDs**.

4. **Run the bot**:

   ```bash
   python main.py
   ```

---

## 📂 File Structure

```
📦 discord-todo-bot
├── main.py              # Discord bot entry point
├── todomate.py             # TodoMate API scraper
├── .env                 # Environment variables (not committed)
├── requirements.txt     # Python dependencies
└── README.md            # Project documentation
```

---

## 📅 Reminder Times

The bot sends automated reminders at:

* **08:00 AM**
* **12:00 PM**
* **04:00 PM**
* **08:00 PM**
* **10:30 PM** (Todo list for the following day)

*All times are based on the `Asia/Manila` timezone.*

---

## ❓ Commands

| Command  | Description                  |
| -------- | ---------------------------- |
| `!today` | Manually fetch today’s todos |
| `!tom`   | Manually fetch tomorrow's todos |
| `!week`  | Manually fetch todos for the next 7 days |
| `!backlog` | Manually fetch unfinished todos from the past 7 days |

---

## 👥 Contributors

* [millaizha](https://github.com/millaizha)
