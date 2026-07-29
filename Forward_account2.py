from telethon import TelegramClient
from telethon.errors import FloodWaitError, ChatWriteForbiddenError, UserBannedInChannelError, UsernameNotOccupiedError, UsernameInvalidError
from telethon.tl.patched import MessageService
from telethon.tl.types import Message
import asyncio
import json
import os

# ─── ACCOUNT 2 CREDENTIALS ───────────────────────────────────────────────────
# Set TELEGRAM_API_ID / TELEGRAM_API_HASH in the environment (see .env.example).
# Get these from https://my.telegram.org → "API development tools"
api_id   = int(os.environ.get("TELEGRAM_API_ID", "0"))
api_hash = os.environ.get("TELEGRAM_API_HASH", "")
# ─────────────────────────────────────────────────────────────────────────────

# Separate session file so Account 1 and Account 2 don't conflict
# ⚠ IMPORTANT: Delete any old session_account2.session file before first run
#   to ensure you log in fresh with Account 2's phone number
client = TelegramClient('session_account2', api_id, api_hash)

# SOURCE GROUP — fetch our message from here
source_chat = 'code_Trust_8897'

# Separate state file so Account 2 tracks its own last-seen IDs
STATE_FILE = 'last_seen_ids_account2.json'

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
    print("Bot Started Successfully (Account 2)...")

    # Quick flood-wait check — try fetching one message to detect an active ban
    print("Checking account status...")
    try:
        await client.get_messages('telegram', limit=1)
        print("Account is healthy. Proceeding.\n")
    except FloodWaitError as e:
        hours = e.seconds // 3600
        mins  = (e.seconds % 3600) // 60
        print(f"⛔ This account is flood-banned for {hours}h {mins}m ({e.seconds}s).")
        print("Stop the script and wait for the ban to expire before retrying.")
        return

    # Fetch our message from source group — skip service messages, must be a real Message
    print(f"Fetching our message from '{source_chat}'...")
    our_msg = None
    async for msg in client.iter_messages(source_chat, limit=50):
        if isinstance(msg, Message) and not isinstance(msg, MessageService) and msg.text:
            our_msg = msg
            break
    if our_msg is None:
        print(f"No forwardable text messages found in '{source_chat}'. Exiting.")
        return
    print(f"Our message loaded (ID: {our_msg.id}): {our_msg.text[:80]}...\nReady.\n")

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
                await asyncio.sleep(10)  # 10s delay — 52 groups × 10s ≈ 8.7 min per cycle

            save_last_seen_ids(last_seen)
            total = success + failed
            rate = round(success / total * 100, 1) if total > 0 else 0
            print(f"\n✓ Success: {success} | ✗ Failed: {failed} | Rate: {rate}%")

        print("\nWaiting 2 minutes before next cycle...")
        await asyncio.sleep(120)


with client:
    client.loop.run_until_complete(main())
