from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, UserBannedInChannelError, UsernameNotOccupiedError, UsernameInvalidError
from telethon.tl.patched import MessageService
import asyncio
import json
import os

# Telegram API credentials — set TELEGRAM_API_ID / TELEGRAM_API_HASH in the
# environment (see .env.example). Get them from https://my.telegram.org.
api_id = int(os.environ.get("TELEGRAM_API_ID", "0"))
api_hash = os.environ.get("TELEGRAM_API_HASH", "")

client = TelegramClient('session_name', api_id, api_hash)

# SOURCE GROUP — fetch our message from here
source_chat = 'code_Trust_8897'

# File to persist last seen message IDs per group
STATE_FILE = 'last_seen_ids.json'

# TARGET GROUPS (52 verified groups)
target_groups = [
    'itandnon', 'Angularjobsupport', 'Interviewproxy', 'sapjobsusa',
    'jobsupport0', 'IT_Job_Board', 'softwarejobupdate', 'reactjsjobssupport',
    'Testing_Manual_Automation', 'frontendjobupdates', 'javaopening',
    'dotnetjobsupport', 'powerbijobs', 'pythonjobsdaily', 'hyderabadjobsit',
    'devopsjobssupport', 'uiuxjobsupport', 'nodejsjobupdates', 'fullstackjobsupport',
    'softwarejobsindia', 'reactjobsdaily', 'remoteitjobs', 'hyditjobs',
    'testingjobsdaily', 'javajobsdaily', 'frontenddeveloperjobs', 'backenddeveloperjobs',
    'devopsjobsdaily', 'softwaretestingjobs', 'freshersitjobs', 'itjobsdailyupdate',
    'techjobsindia', 'pythondeveloperjobs', 'powerbideveloperjobs', 'reactdeveloperjobs',
    'fullstackdeveloperjobs', 'softwareengineerjobs', 'manualtestingjobs',
    'automationtestingjobs', 'itjobsupportgroup', 'nodejsdeveloperjobs',
    'uiuxdesignerjobs', 'jobupdatesdaily', 'hyderabadsoftwarejobs',
    'softwarecareerupdates', 'dailyitopenings', 'reactjsjobsindia',
    'softwarejobsearch', 'latestitjobs', 'developerjobsindia',
    'jobsforsoftwareengineers', 'techcareerjobs',
]


def load_last_seen_ids():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_last_seen_ids(data):
    with open(STATE_FILE, 'w') as f:
        json.dump(data, f)


async def forward_to_group(group, msg):
    try:
        await client.forward_messages(group, msg)
        print(f"  ✓ Forwarded to {group}")
        return True
    except FloodWaitError as e:
        print(f"  ⚠ FloodWait {group}: skipping (wait was {e.seconds}s)")
        return False
    except (ChatWriteForbiddenError, UserBannedInChannelError,
            UsernameNotOccupiedError, UsernameInvalidError) as e:
        print(f"  ✗ {group}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ {group}: {e}")
        return False


async def main():
    await client.start()
    print("Bot Started Successfully...")

    # Fetch our message from source group once — skip service messages
    print(f"Fetching our message from '{source_chat}'...")
    source_messages = await client.get_messages(source_chat, limit=10)
    source_messages = [m for m in source_messages if not isinstance(m, MessageService)]
    if not source_messages:
        print(f"No forwardable messages in '{source_chat}'. Exiting.")
        return
    our_msg = source_messages[0]
    print(f"Our message loaded (ID: {our_msg.id}). Ready.\n")

    cycle = 0
    while True:
        cycle += 1
        print(f"\n--- Cycle {cycle} ---")

        # Check all groups for new activity
        last_seen = load_last_seen_ids()
        active_groups = []

        print(f"Scanning {len(target_groups)} groups for new activity...")
        for group in target_groups:
            try:
                messages = await client.get_messages(group, limit=1)
                if messages:
                    latest_id = messages[0].id
                    last_id = last_seen.get(group, 0)
                    if latest_id > last_id:
                        active_groups.append(group)
                        last_seen[group] = latest_id
            except Exception:
                pass

        if not active_groups:
            print("No new activity. Skipping forward.")
        else:
            print(f"New activity in {len(active_groups)} group(s). Forwarding our message...")
            success, failed = 0, 0
            for group in target_groups:
                result = await forward_to_group(group, our_msg)
                if result:
                    success += 1
                else:
                    failed += 1
                await asyncio.sleep(10)  # 10s delay to avoid flood wait

            save_last_seen_ids(last_seen)
            total = success + failed
            rate = round(success / total * 100, 1) if total > 0 else 0
            print(f"\n✓ Success: {success} | ✗ Failed: {failed} | Rate: {rate}%")

        print("\nWaiting 2 minutes before next cycle...")
        await asyncio.sleep(120)


with client:
    client.loop.run_until_complete(main())
