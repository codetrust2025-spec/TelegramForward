# AI vs human handoff (fix for “bot” complaints)

## Immediate ops (one lead)

1. Open **Inbox → Aak Sai** (account7) → turn **AI smart reply OFF** for that lead (or CRM equivalent).
2. **Kalyan or Vani** reply manually: acknowledge lag, confirm tomorrow 5 PM D365 functional, repeat-client discount only if approved.
3. Do **not** re-enable AI on that lead until the deal is closed.

## Product fixes (deployed in `core/ai_smart_reply.py`)

| Problem | Fix |
|--------|-----|
| User says “turn off bot” | Auto **`disable_for_lead`** (`user_opt_out`) — AI stays off until you re-enable |
| Paid thread with Kalyan-style human chat (4+ human out + payment/UltraViewer/Meet) | Auto **`human_owned`** — sweep and live listener skip AI |
| Service complaint on a human-owned thread | **`service_complaint`** lock — no auto replies |
| Vani “on another call / just wait” | Extended **operator defer** markers — AI pauses until a real human follow-up |
| Midnight “which tech stack?” on old paid chats | Inbox **sweep** skips leads with AI disabled / sticky lock |
| `escalated` cleared on every new message | **Sticky** disable reasons are not auto-cleared |

Re-enable AI per lead only from **AI settings / lead toggle** when you want Karthik back on that chat.
