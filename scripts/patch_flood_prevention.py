"""Patch account_worker.py for flood prevention."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "workers" / "account_worker.py"
c = p.read_text(encoding="utf-8")

replacements = [
    (
        """    FLOOD_COOLDOWN_STREAK,
    FLOOD_HARD_BAN_SECONDS,""",
        """    FLOOD_COOLDOWN_STREAK,
    FLOOD_END_CYCLE_SECONDS,
    FLOOD_HARD_BAN_SECONDS,
    FLOOD_HEALTH_LOW_THRESHOLD,
    FLOOD_STREAK_MAX_HEALTHY,
    FLOOD_STREAK_MAX_LOW_HEALTH,""",
    ),
]

if "_flood_streak_limit" not in c:
    helper = """
    def _flood_streak_limit(self) -> int:
        if self.intel.health_score < FLOOD_HEALTH_LOW_THRESHOLD:
            return FLOOD_STREAK_MAX_LOW_HEALTH
        return FLOOD_STREAK_MAX_HEALTHY

"""
    c = c.replace(
        "    def _filter_groups(self, groups: list) -> list:",
        helper + "    def _filter_groups(self, groups: list) -> list:",
        1,
    )

replacements.extend([
    (
        """            health = await check_account_health(client, self.logger)



            if health == "not_authorized":""",
        """            health = await check_account_health(client, self.logger)
            flood_secs = 0
            if isinstance(health, tuple):
                flood_secs = int(health[1]) if len(health) > 1 else 0
                health = health[0]

            if health == "not_authorized":""",
    ),
    (
        """            if health == "flood_banned":

                wait_s = min(FLOOD_WAIT_MAX_SECONDS, FLOOD_WAIT_DEFAULT_SECONDS)

                await self._wait_countdown(

                    wait_s, "flood_wait",

                    f"Flood limit — resuming in {wait_s // 60}m",

                )

                return False""",
        """            if health == "flood_banned":
                wait_s = min(
                    FLOOD_ACCOUNT_WAIT_CAP,
                    max(flood_secs, FLOOD_WAIT_DEFAULT_SECONDS),
                )
                human = format_duration(wait_s)
                if flood_secs >= FLOOD_HARD_BAN_SECONDS:
                    await self._log(
                        f"🛑 Account already rate-limited (~{human}) — not starting cycle",
                        "warning",
                        action="account_sleep",
                        reason="health_heavy_flood",
                    )
                    await self._pause_for_flood(
                        wait_s,
                        f"🛑 Rate limit (~{human})",
                        heavy=True,
                    )
                else:
                    await self._wait_countdown(
                        wait_s, "flood_wait",
                        f"⏸ Rate limited (~{human}) — cycle skipped",
                    )
                return False""",
    ),
    (
        """                hard_ban = secs >= FLOOD_HARD_BAN_SECONDS

                st.flood_streak += 1""",
        """                hard_ban = secs >= FLOOD_HARD_BAN_SECONDS
                medium_ban = secs >= FLOOD_END_CYCLE_SECONDS
                api_hit = meta.get("api", "?")

                st.flood_streak += 1""",
    ),
    (
        """                        f"🛑 Heavy rate limit on: {group} — API: {meta.get('api', '?')} — ~{human} wait",""",
        """                        f"🛑 Heavy rate limit on: {group} — API: {api_hit} — ~{human} wait",""",
    ),
])

needle = """                    st.flood_streak = 0

                    return "flood_break"



                if st.flood_streak < FLOOD_COOLDOWN_STREAK:"""

insert = """                    st.flood_streak = 0

                    return "flood_break"

                if medium_ban and not hard_ban:
                    pause = min(secs + 30, FLOOD_ACCOUNT_WAIT_CAP)
                    await self._log(
                        f"⏸ Medium rate limit ({api_hit}) ~{human} — stopping cycle to avoid 15h+ ban",
                        "warning",
                        group=group,
                        action="cycle_end",
                        reason="medium_flood",
                        delay_used=pause,
                    )
                    await self._pause_for_flood(
                        pause,
                        f"⏸ Rate limit (~{human})",
                        heavy=False,
                    )
                    st.flood_streak = 0
                    return "flood_break"

                streak_limit = self._flood_streak_limit()
                if st.flood_streak < streak_limit:"""

for old, new in replacements:
    if old not in c:
        raise SystemExit(f"block not found: {old[:60]!r}...")
    c = c.replace(old, new, 1)

if needle in c:
    c = c.replace(needle, insert, 1)
else:
    print("needle already patched or missing")

p.write_text(c, encoding="utf-8")
print("done")
