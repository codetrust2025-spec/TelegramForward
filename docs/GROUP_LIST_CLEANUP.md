# Group list cleanup checklist (before next upload)

Use this **before** replacing `data/groups_list.json` so accounts spend time on groups that can accept posts—not on admin/broadcast channels that always fail.

---

## Why bother?

| Keep messy list (334+) | Clean list (~100–150 postable) |
|------------------------|--------------------------------|
| Many `🚫 Cannot post` every cycle | More `📤 Message posted` per hour |
| Wastes API calls → rate limits / Sleep | Lower ban risk |
| Success % looks bad | Failures mean real issues, not “read-only channel” |
| Same bad group tried on 9 accounts | Bad names removed once |

---

## Step 1 — Export what already failed (5 min)

For **each logged-in account** in the dashboard:

1. Select the account.
2. Click **Dead list** (Column 2 → Progress).
3. Save the downloaded file (e.g. `dead_account5.txt`).

Merge those names into one list: **“never post here.”**

> Your project already learned **~231** group names that don’t work (blocked on at least one account). **~103** names in the master file were never marked dead yet—they may still be postable or untested.

---

## Step 2 — Remove these from the master file

Delete any username that appears in:

- [ ] Any **Dead list** export (blocked + invalid for that account)
- [ ] Dashboard logs as `🚫 Cannot post (admin/broadcast)` (repeated failures)
- [ ] `🗑 Invalid group removed` (dead username)
- [ ] Names that are clearly **announcement channels** (no member chat), e.g. many `*jobs*`, `*channel*`, exam/voucher groups you never saw a successful post in

**Do not remove** a group if:

- [ ] You see `📤 Message posted` or `✅ Joined & posted` in logs for that name
- [ ] It’s in **Active list** for an account and still getting posts
- [ ] You’re unsure — keep it once; the bot will block it per account if needed

---

## Step 3 — Keep groups that work

Prefer groups where:

- [ ] Members can **send messages** (discussion groups, support groups)
- [ ] You or the bot **posted successfully** at least once
- [ ] Topic matches your message (IT jobs / interview support / tech)—but **format** must allow posting, not only reading

Target size: **quality over quantity**. Often **100–200** good groups beat **334** mixed.

---

## Step 4 — Format the new file

- [ ] One username per line, or numbered list (`1. groupname`) — same as current upload format
- [ ] No `@` required (bot accepts both)
- [ ] No duplicates
- [ ] No empty lines or header junk

---

## Step 5 — Upload and restart workers

1. [ ] Dashboard → **Groups upload** → upload the new file (replaces master list)
2. [ ] Confirm total count in UI (e.g. “150 groups”)
3. [ ] **Hard refresh** dashboard
4. [ ] Let running accounts finish current cycle, or **Stop All** → **Start All** after upload if you want a clean cycle start

**Note:** Uploading a new master list does **not** clear per-account `blocked_groups.json`. That’s good—those groups stay skipped. New list should **omit** them so they’re not in rotation at all.

---

## Step 6 — Optional: purge blocked from disk (advanced)

Only if you want a **full reset** of “dead” memory (bot will re-test everything):

- Back up `data/accounts/accountN/blocked_groups.json`
- Clear arrays to `[]` per account, **or** delete files and let the app recreate empty ones

Usually **not needed** if Step 2 removed those names from the upload.

---

## Quick decision table

| Log pattern | Action in new list |
|-------------|-------------------|
| `📤 Message posted` | **Keep** |
| `↷ Skipped — our message in recent history` | **Keep** (already reached) |
| `🚫 Cannot post (admin/broadcast)` | **Remove** |
| `🗑 Invalid group removed` | **Remove** |
| `✗ Too many requests` | **Keep** (rate limit is temporary) |
| Never tried yet | **Keep** unless name looks like broadcast-only channel |

---

## After cleanup — what to expect

- Faster cycles (fewer join + fail attempts)
- Higher **Messages sent (24h)** per account
- Higher success % on **postable** groups
- Accounts “finish” slice slower because work is real posting, not marking dead channels

---

## Generate a suggested keep-list (optional)

From project root:

```bash
python scripts/suggest_clean_groups.py
```

Writes `data/groups_list_suggested_keep.txt` — master minus groups blocked on any account (review before upload).
