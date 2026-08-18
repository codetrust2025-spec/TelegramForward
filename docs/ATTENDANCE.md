# Attendance capture

Daily attendance for handlers: a once-a-day Start Work prompt, office-network
verification, and monthly attendance percentages for HR.

**This feature computes percentages and nothing else.** It does not read or
write salary, and it does not touch commission. Attendance-linked pay is a
separate, still-undecided policy — see *Deliberately not built* below.

## What a day looks like

1. An employee opens the dashboard. The client asks `GET /api/attendance/today`.
2. If attendance is configured, the login is enrolled, today is a scheduled
   working day, and no record exists yet, the prompt appears: *"Good morning,
   {name} — ready to start your work day?"*
3. **Start Work** is enabled only when the request arrives from an approved
   office IP. Off-network it is disabled with *"You must be connected to the
   office network to start your workday."*
4. `POST /api/attendance/start` re-verifies the network server-side and writes
   one record for the IST day: timestamp, employee id, arrival state, device
   metadata, and the network result.
5. The prompt does not return that day. It returns the next scheduled working
   day.

Dismissing the prompt with **Not now** also suppresses it until the next IST
day — "once per day" is taken literally. A day dismissed or missed can still be
recorded by an admin through the override path.

Dashboards get left open overnight, so the client watches for the IST date to
change (once a minute, and whenever the tab becomes visible again) and re-asks
the server. The next working day's prompt therefore appears on its own, with no
refresh and no new login.

## Employee identity

Handlers were only `{username, reference, password}`, and money buckets by the
lowercased `reference` — that is, by a *name*. Fine for a table row, wrong for
scoping a payout rule: rename the reference and the rule follows the name to
whoever holds it next.

`features/employee_identity.py` introduces `employee_id` (`EMP-0001`), assigned
once, never derived from a name, never reused. Usernames and references become
**aliases**. Renaming somebody adds an alias; the id does not move.

**Any attendance-linked payout rule must be scoped to `employee_id`** — never to
display name, reference, username, or role. Scoping by role was explicitly
rejected: a second admin would inherit the rule.

### `data/employee_ids.json`

Operational data. Never shipped in a release, because it names real people.
Prefer `POST /api/attendance/employees` over editing by hand.

```json
{
  "sequence": 2,
  "employees": [
    {
      "employee_id": "EMP-0001",
      "display_name": "Example Person",
      "usernames": ["example"],
      "references": ["example"],
      "assigned_at": "2026-08-10T00:00:00+00:00",
      "active": true
    }
  ]
}
```

`sequence` is the high-water mark of assigned ids. It exists so that deleting a
row cannot release that id to the next joiner — otherwise every record and rule
still holding it would quietly start pointing at a different person.

## Calendar and shift policy

Working days are **not hard-coded**. A six-day week is as plausible here as a
five-day one, holidays differ by state and year, and a wrong denominator
silently changes every percentage. With no `working_weekdays` configured,
attendance stays unconfigured and the prompt does not appear.

### `data/attendance_config.json`

```json
{
  "working_weekdays": [0, 1, 2, 3, 4, 5],
  "holidays": ["2026-08-15", "2026-10-02"],

  "shift_start": "09:30",
  "grace_minutes": 15,
  "early_threshold_minutes": 30,
  "credited_states": ["early", "on_time", "grace"],

  "office_ip_allowlist": ["203.0.113.0/24", "198.51.100.7"],
  "trusted_proxy_hops": 1,
  "trusted_proxy_ips": ["127.0.0.1", "::1"]
}
```

| Key | Meaning |
|---|---|
| `working_weekdays` | Monday=0 … Sunday=6. Empty means unconfigured. |
| `holidays` | IST dates excluded from the denominator. |
| `credited_states` | Which arrival states count toward the percentage. Late is excluded by default — a policy choice, so it is configuration. |
| `office_ip_allowlist` | Approved public IPs or CIDRs. Empty means unverifiable, and Start Work stays blocked for everyone. |
| `trusted_proxy_hops` | Proxies in front of the app (nginx = 1). |
| `trusted_proxy_ips` | Which immediate peers may have their `X-Forwarded-For` believed. Defaults to loopback, which is where nginx connects from. |

### Arrival states

Contiguous and non-overlapping, so every arrival lands in exactly one:

| State | Window (relative to `shift_start`) |
|---|---|
| `early` | earlier than `early_threshold_minutes` before |
| `on_time` | within that window, up to and including `shift_start` |
| `grace` | up to `grace_minutes` after |
| `late` | beyond that |

### Attendance percentage

```
attendance % = credited days / scheduled working days elapsed so far
```

Measured against **elapsed** days, so a month in progress is not scored against
days nobody has worked yet. A record on a non-working day is stored but does not
inflate the numerator; it is reported as `off_schedule_records`.

## Office-network verification

**A browser cannot read the Wi-Fi SSID.** There is no web API for it, on any
browser. "Connected to office Wi-Fi" is therefore only checkable as "arriving
from an approved public IP", and that check must happen server-side — anything
the page reports about itself is writable by whoever is sitting at the page.

The subtlety is `X-Forwarded-For`, and it has two halves.

**Which entry.** A client can send that header itself, so trusting the leftmost
entry would let anyone claim an office IP with one curl flag.
`features/office_network.py` counts in from the **right** by
`trusted_proxy_hops`, because nginx appends the peer it actually saw
(`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`).

**Whether to believe it at all.** Counting from the right only helps if a proxy
appended something. This app binds `0.0.0.0:8000`, so it is reachable directly
as well as through nginx, and a request that skipped nginx carries a header
consisting solely of what its sender typed. `X-Forwarded-For` is therefore only
honoured when the connection came *from* a peer in `trusted_proxy_ips`.
Otherwise the peer address itself is used, which for a direct request is the
caller's real address and will not be in the office allowlist.

> **Infrastructure note.** On the current production host the app answers on the
> public IP at port 8000 (`ufw` inactive, `iptables` INPUT policy `ACCEPT`), so
> nginx can be bypassed. The trusted-peer rule above means attendance cannot be
> forged that way, but binding the app to `127.0.0.1` or firewalling 8000 is
> still worth doing on its own merits. No production configuration was changed
> by this feature.

Every ambiguity fails closed: unparseable IP, no allowlist configured, or no
client address at all all come back unverified. An attendance record that cannot
prove where it came from is worth less than no record.

Device metadata (user agent, platform, screen) is captured as a hint about which
machine was used. It is **not** evidence of location and is never used for
verification.

## Admin override

For the exceptional case — office ISP outage, an IP change nobody expected —
an admin can authorise a day through `POST /api/attendance/override`. The audit
trail is the point:

- `reason`
- `approved_by` and `approved_by_employee_id`
- `approved_at`
- `original_network_result` — what the network check actually said at the time

An override annotates an existing record rather than duplicating the day, and it
does **not** rewrite the arrival state: it authorises the day, it does not
change when the person arrived.

## API

| Method | Path | Who |
|---|---|---|
| GET | `/api/attendance/today` | any signed-in employee |
| POST | `/api/attendance/start` | any signed-in employee |
| GET/PUT | `/api/attendance/config` | fleet admin |
| GET/POST | `/api/attendance/employees` | fleet admin |
| POST | `/api/attendance/employees/{id}/aliases` | fleet admin |
| GET | `/api/attendance/records?month=` | fleet admin |
| GET | `/api/attendance/summary?month=` | fleet admin |
| POST | `/api/attendance/override` | fleet admin |

## Setup

1. Create `data/attendance_config.json` with the working week, holidays, shift
   start and the office IP allowlist.
2. Enrol employees: `POST /api/attendance/employees` with `display_name` plus a
   `username` and/or `reference`.
3. Confirm in **Attendance** in the sidebar that the calendar reads correctly
   and the denominator matches expectations before anyone relies on a figure.

## Deliberately not built

**Attendance is not applied to any payout.** Two things must be settled first:

1. **The commission source-of-truth discrepancy.** For candidate *sakthivek*,
   `handler_earning_allocations` credits ₹10,000 while `stats`'s
   `base_commission_total` credits ₹25,000. Scaling by attendance would multiply
   whichever is wrong, and make the mismatch harder to spot — both figures would
   then look like deliberate adjusted numbers.
2. **The written policy.** Payout rules are compliance-sensitive; the formula
   belongs in an approved company policy before it is in code.

When both are settled, the rule is expected to be:

```
payable commission = approved commission × attendance percentage
```

scoped to a single `employee_id`, and to no one else.

## Known gaps

- The HR view is wired into the desktop sidebar only. Mobile navigation has no
  entry yet; the Start Work prompt itself works on both.
- Holidays and the IP allowlist are edited as JSON on the host. The HR view can
  toggle working weekdays but does not yet edit those two lists.
- There is no "end of day" — attendance is presence, not hours worked.
