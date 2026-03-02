import os
import asyncio
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

SOURCE_CHANNEL = int(os.getenv("SOURCE_CHANNEL"))
TARGET_CHANNEL = int(os.getenv("TARGET_CHANNEL"))

MAX_FILES = int(os.getenv("MAX_FILES", 100))
TIME_WINDOW = int(os.getenv("TIME_WINDOW_HOURS", 12))

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

LAST_ID_FILE = "last_id.txt"

upload_count = 0
window_start = datetime.now()


# --------------------------
# Utility Functions
# --------------------------

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024


def get_last_processed_id():
    if os.path.exists(LAST_ID_FILE):
        with open(LAST_ID_FILE, "r") as f:
            return int(f.read().strip())
    return 1  # Start from ID 1


def save_last_processed_id(message_id):
    with open(LAST_ID_FILE, "w") as f:
        f.write(str(message_id))


async def reset_window_if_needed():
    global upload_count, window_start
    if datetime.now() > window_start + timedelta(hours=TIME_WINDOW):
        upload_count = 0
        window_start = datetime.now()
        print("🔄 Upload window reset")


# --------------------------
# Health Server
# --------------------------

async def health(request):
    return web.Response(text="Bot is running ✅")


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# --------------------------
# Main Logic
# --------------------------

async def main():
    global upload_count, window_start

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    await client.start()
    print("✅ Logged in successfully")

    current_id = get_last_processed_id()

    while True:
        await reset_window_if_needed()

        if upload_count >= MAX_FILES:
            wait_time = (
                window_start + timedelta(hours=TIME_WINDOW) - datetime.now()
            ).total_seconds()

            print(f"⏳ Limit reached. Sleeping {int(wait_time)} seconds")
            await asyncio.sleep(wait_time)

            upload_count = 0
            window_start = datetime.now()

        try:
            message = await client.get_messages(SOURCE_CHANNEL, ids=current_id)

            # If message missing / deleted
            if not message:
                print(f"⚠ Skipped missing ID {current_id}")
                current_id += 1
                continue

            # If no media
            if not message.media:
                current_id += 1
                continue

            file_path = await client.download_media(message.media, file=DOWNLOAD_DIR)

            if not file_path:
                current_id += 1
                continue

            original_name = os.path.basename(file_path)
            new_name = f"[TG - @Mid_Night_Hub]{original_name}"
            new_path = os.path.join(DOWNLOAD_DIR, new_name)

            os.rename(file_path, new_path)

            file_size = os.path.getsize(new_path)
            formatted_size = format_size(file_size)

            caption = (
                f"File Name : {new_name}\n"
                f"File Size : {formatted_size}"
            )

            await client.send_file(
                TARGET_CHANNEL,
                new_path,
                caption=caption,
                attributes=[DocumentAttributeFilename(new_name)]
            )

            upload_count += 1
            print(f"✅ Uploaded ID {current_id}: {new_name}")

            os.remove(new_path)

            save_last_processed_id(current_id)
            current_id += 1

            print("⏳ Waiting 10 seconds before next upload...")
            await asyncio.sleep(10)

        except FloodWaitError as e:
            print(f"⚠ FloodWait: Sleeping {e.seconds} seconds")
            await asyncio.sleep(e.seconds)

        except Exception as e:
            print(f"❌ Error at ID {current_id}: {e}")
            current_id += 1
            await asyncio.sleep(2)


# --------------------------
# Run Bot
# --------------------------

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_health_server())
    loop.run_until_complete(main())
