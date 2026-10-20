import os
import re
import asyncio
from datetime import datetime, timedelta
from telegram.ext import ApplicationBuilder, MessageHandler, filters

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 5000))
HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")


def parse_start_condition(start_str):
    # Updated regex to make the minutes part optional (.(\d{2}))?
    match = re.match(r"(\d{1,2})(?:\.(\d{2}))?\s*(am|pm)\s*(\w+)", start_str.strip(), re.I)
    if not match:
        raise ValueError(f"Invalid start condition: '{start_str}'")

    hour, minute, am_pm, day_str = match.groups()
    hour = int(hour)
    # If minutes weren't provided (e.g., "8am"), default to 0
    minute = int(minute) if minute is not None else 0

    if am_pm.lower() == "pm" and hour != 12:
        hour += 12
    elif am_pm.lower() == "am" and hour == 12:
        hour = 0

    ref_monday = datetime(2024, 1, 1, hour, minute)
    days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    day_idx = days.index(day_str.lower()[:3])

    return ref_monday + timedelta(days=day_idx)


def format_time_str(dt):
    hour_12 = dt.hour % 12 or 12
    minute_str = f"{dt.minute:02d}"
    am_pm = "am" if dt.hour < 12 else "pm"
    return f"{hour_12}.{minute_str}{am_pm}"


async def handle_message(update, context):
    text = update.message.text
    try:
        # Split into non-empty lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        if not lines:
            return

        # First line: start time and day
        current_dt = parse_start_condition(lines[0])

        output_lines = []
        days_map = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

        current_day_name = days_map[current_dt.weekday()]
        output_lines.append(current_day_name)

        # Process actions
        for line in lines[1:]:
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                continue

            action_name, duration_expr = parts[0], parts[1]

            # Calculate duration math
            duration_minutes = eval(duration_expr, {"__builtins__": None}, {})

            day_name = days_map[current_dt.weekday()]

            if day_name != current_day_name:
                current_day_name = day_name
                output_lines.append("")
                output_lines.append(current_day_name)

            output_lines.append(f"{format_time_str(current_dt)} {action_name}")

            current_dt += timedelta(minutes=int(duration_minutes))

        # Append final end time and day
        end_day_name = days_map[current_dt.weekday()]
        if end_day_name != current_day_name:
            output_lines.append("")
            output_lines.append(end_day_name)

        output_lines.append(f"{format_time_str(current_dt)} end")

        reply_text = "\n".join(output_lines)
        await update.message.reply_text(reply_text)

    except Exception as e:
        await update.message.reply_text(f"Error processing input: {e}")


async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Explicitly initialize and start without closing the loop
    await app.initialize()
    await app.start()
    await app.updater.start_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"https://{HOSTNAME}/{BOT_TOKEN}"
    )

    # Keep running until interrupted
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
