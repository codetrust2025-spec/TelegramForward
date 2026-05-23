"""

24/7 self-healing account worker — one account, one loop, zero cross-account deps.

Stops ONLY on explicit user STOP.



Smart sending: randomized groups, pre-checks, scoring, human-like delays.

"""



import asyncio
import time

import threading

from collections import deque

from datetime import datetime



from core.config import (
    SESSION_LOCK_GROUP_COOLDOWN,
    SESSION_LOCK_RECONNECT_WAIT,
    SESSION_LOCK_STREAK_END_CYCLE,
    SESSION_LOCK_STREAK_PAUSE,

    CRASH_RESTART_SECONDS,


    FLOOD_ACCOUNT_WAIT_CAP,

    FLOOD_COOLDOWN_MAX_SECONDS,

    FLOOD_COOLDOWN_MIN_SECONDS,

    FLOOD_COOLDOWN_STREAK,

    FLOOD_END_CYCLE_SECONDS,

    FLOOD_HARD_BAN_SECONDS,

    FLOOD_HEALTH_LOW_THRESHOLD,

    FLOOD_STREAK_MAX_HEALTHY,

    FLOOD_STREAK_MAX_LOW_HEALTH,

    FLOOD_WAIT_DEFAULT_SECONDS,

    FLOOD_WAIT_MAX_SECONDS,

    MAX_LOG_ENTRIES,

    NO_GROUPS_RETRY_SECONDS,

    NOT_AUTH_RETRY_SECONDS,

)

from core.formatting import format_duration

from core.account_info_store import clear_account_info, load_account_info, save_account_info
from core.group_assignment import partition_summary
from core.groups_store import (
    groups_readonly_snapshot_for_slot,
    load_account_dead,
    load_master_groups,
    purge_invalid_from_master,
    purge_stored_invalid_groups,
    save_account_dead,
)

from core.config import MESSAGE_REWRITE_ENABLED
from core.message_rewrite import prepare_cycle_message

from core.smart_engine import GroupIntelligence
from core.account_timing import AccountTimingPolicy
from core.structured_logging import (
    LogEvent,
    LogLevel,
    build_log_entry,
    infer_event_from_legacy,
)

from core.telegram_client import get_client, is_session_error, reconnect_client, run_group_operation

from features.delay_handler import wait_seconds, wait_with_countdown

from features.group_operation import process_group

from features.health_check import check_account_health

from features.logging_feature import AccountLogger

from workers.account_state import AccountState

from events.event_bus import event_bus
from events.event_types import EventType
from messaging.account_queue import AccountQueue, queue_manager
from messaging.message_router import message_router
from core.observability.account_metrics import metrics_store
from messaging.fair_scheduler import CycleFairScheduler
from messaging.retry_manager import classify_task_result, retry_manager
from messaging.task_types import QueueTask, TaskType





def _parse_op_result(result) -> tuple[str, dict]:

    if isinstance(result, tuple) and len(result) >= 1:

        code = result[0]

        meta = result[1] if len(result) > 1 and isinstance(result[1], dict) else {}

        return code, meta

    return result, {}





def _flood_pause_seconds(telegram_secs: int, *, streak: bool) -> int:

    """How long to pause the account before the next cycle."""

    s = max(0, int(telegram_secs))

    if s >= FLOOD_HARD_BAN_SECONDS:

        return min(s, FLOOD_ACCOUNT_WAIT_CAP)

    if streak:

        return min(max(s, FLOOD_COOLDOWN_MIN_SECONDS), FLOOD_COOLDOWN_MAX_SECONDS)

    return 0





class AccountWorker:

    """One account = one non-stop worker. Fully isolated from other accounts."""



    def __init__(self, slot: str, on_state_change=None, queue: AccountQueue | None = None):

        self.slot = slot

        self.state = AccountState(slot=slot)

        self.intel = GroupIntelligence(slot)

        self.logger = AccountLogger(slot=slot)

        self.logger.set_callback(self._on_logger_entry)

        self._on_state_change = on_state_change

        self._start_lock = threading.Lock()

        self._announced_start = False

        self._last_log_msg = ""

        self._recent_logs: deque = deque(maxlen=30)
        self._session_lock_streak = 0
        self._pending_joined_scan = False
        self._one_shot = False
        self._queue_active = False
        self._queue_task: asyncio.Task | None = None
        self._manager = None
        self._cycle_lock = asyncio.Lock()
        self._execution_gate = asyncio.Lock()
        self._queue = queue or queue_manager.get_queue(slot)
        self._cycle_end_reason = "complete"
        self._cycle_groups_done = 0
        self._cycle_metrics_active = False
        self._fair_scheduler = CycleFairScheduler(slot)
        self._timing_policy = AccountTimingPolicy(slot)
        self._metrics = metrics_store.scope(slot)
        self._execution_policy = None
        self._speed_profile = None
        self._next_send_delay: int | None = None
        self._cycle_had_flood = False
        self._scheduler_ctx = None
        self._cycle_context: dict | None = None

        invalid, blocked = load_account_dead(slot)
        if invalid:
            purge_stored_invalid_groups(slot)
            invalid, blocked = load_account_dead(slot)

        self.state.invalid_groups = invalid

        self.state.blocked_groups = blocked

        cached = load_account_info(slot)
        if cached:
            self.state.account_info = cached

        try:
            from core.account_profile import apply_profile_to_intel

            apply_profile_to_intel(self.intel)
        except Exception:
            pass

        self._sync_health_to_state()

    def set_manager(self, manager) -> None:
        self._manager = manager

    def _cycle_success_rate(self) -> float | None:
        st = self.state
        total = st.success + st.failed
        if total <= 0:
            return None
        return st.success / total * 100.0

    def _avg_cycle_success_rate(self) -> float | None:
        from core.cycle_metrics import cycle_metrics_store
        from core.execution_policy import _avg_success_rate

        history = cycle_metrics_store.history(self.slot, limit=5)
        return _avg_success_rate(history)

    def _build_speed_profile(self):
        from core.cycle_metrics import cycle_metrics_store
        from core.execution_policy import _avg_success_rate
        from core.speed_optimizer import compute_speed_profile

        st = self.state
        history = cycle_metrics_store.history(self.slot, limit=5)
        avg_sr = _avg_success_rate(history)
        policy = self._execution_policy
        timing = self._timing_policy.snapshot()
        return compute_speed_profile(
            health_score=st.health_score,
            health_tier=self.intel.health_tier(),
            cycle_success_rate=self._cycle_success_rate() or avg_sr,
            avg_success_rate=avg_sr,
            flood_streak=st.flood_streak,
            cycles_without_flood=self.intel.cycles_without_flood,
            fleet_pressure=policy.fleet_pressure if policy else timing.fleet_pressure,
            unhealthy=bool(policy and policy.unhealthy),
            heavy_rate_limit=st.heavy_rate_limit,
            recently_flooded=timing.recently_flooded,
            last_cycle=cycle_metrics_store.latest(self.slot),
        )

    def _apply_policy_delay_mult(self, delay: int, *, cycle: bool = False) -> int:
        if not self._execution_policy:
            return delay
        mult = (
            self._execution_policy.cycle_delay_multiplier
            if cycle
            else self._execution_policy.send_delay_multiplier
        )
        mode = self._speed_profile.mode if self._speed_profile else "normal"
        if mode == "fast":
            mult = min(mult, 1.0)
        elif mode == "cautious":
            mult = max(mult, 1.0)
        return max(1, int(delay * mult))

    def _group_step_delay(self, result: str, *, skip_reason: str = "") -> int:
        from core.throughput_engine import compute_skip_delay

        if result == "skipped" or skip_reason:
            return compute_skip_delay(
                speed_mode=self._speed_profile.mode if self._speed_profile else "normal",
                health_score=self.state.health_score,
                skip_reason=skip_reason or result,
            )
        return self._policy_scaled_send_delay()

    def _compute_send_delay(self) -> int:
        from core.speed_optimizer import compute_send_delay

        profile = self._speed_profile
        if profile:
            policy_mult = self._execution_policy.send_delay_multiplier if self._execution_policy else 1.0
            if profile.mode == "fast":
                policy_mult = min(policy_mult, 1.0)
            return compute_send_delay(
                profile,
                flood_streak=self.state.flood_streak,
                policy_mult=policy_mult,
            )
        return self.intel.compute_send_delay(
            flood_streak=self.state.flood_streak,
            cycle_success_rate=self._cycle_success_rate(),
        )

    def _policy_scaled_send_delay(self) -> int:
        if self._next_send_delay is not None:
            delay = self._next_send_delay
            self._next_send_delay = None
            return self._apply_policy_delay_mult(delay, cycle=False)
        delay = self._compute_send_delay()
        return self._apply_policy_delay_mult(delay, cycle=False)

    def _compute_cycle_delay(self) -> int:
        from core.speed_optimizer import compute_cycle_delay

        profile = self._speed_profile
        if profile:
            policy_mult = self._execution_policy.cycle_delay_multiplier if self._execution_policy else 1.0
            if profile.mode == "fast":
                policy_mult = min(policy_mult, 1.0)
            return compute_cycle_delay(profile, policy_mult=policy_mult)
        return self.intel.compute_cycle_delay(cycle_success_rate=self._cycle_success_rate())

    def _policy_scaled_cycle_delay(self) -> int:
        delay = self._compute_cycle_delay()
        delay = self._apply_policy_delay_mult(delay, cycle=True)
        return delay + self._timing_policy.cycle_stagger_seconds()

    async def _prep_next_send_async(self) -> None:
        """Precompute delays and UAS decisions for upcoming groups during waits."""
        ctx = self._cycle_context
        st = self.state
        if not ctx or not ctx.get("groups"):
            self._next_send_delay = self._compute_send_delay()
            return

        idx = int(ctx.get("index", 0))
        groups = ctx["groups"]
        prefetch: dict = {}

        from core.unified_scheduler import decide

        for offset in (1, 2):
            j = idx + offset
            if j >= len(groups):
                break
            g = groups[j]
            pre = self.intel.precheck_skip_reason(g, account_sleeping=st.heavy_rate_limit)
            dec = None
            if self._scheduler_ctx:
                dec = decide(g, self._scheduler_ctx, self.intel)
            prefetch[g] = {
                "precheck": pre,
                "action": dec.action.value if dec else "auto",
                "reason": dec.reason if dec else "",
            }

        ctx["prefetch"] = prefetch

        if idx + 1 < len(groups):
            nxt = groups[idx + 1]
            meta = prefetch.get(nxt, {})
            if meta.get("precheck") or meta.get("action") == "skip":
                self._next_send_delay = self._group_step_delay(
                    "skipped",
                    skip_reason=meta.get("precheck") or meta.get("reason") or "skip",
                )
            else:
                self._next_send_delay = self._compute_send_delay()
        else:
            self._next_send_delay = self._compute_send_delay()

    def _load_cycle_checkpoint(self, groups_count: int) -> tuple[int, int | None]:
        """Return (start_index, resume_cycle). resume_cycle set when resuming after crash/restart."""
        import json
        import os
        from core.config import STATE_DIR

        path = os.path.join(STATE_DIR, self.slot, "cycle_checkpoint.json")
        if not os.path.exists(path):
            return 0, None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            total = int(data.get("total_groups") or 0)
            if total != groups_count:
                return 0, None
            ts = float(data.get("timestamp") or 0)
            if ts and (time.time() - ts) > 86400:
                return 0, None
            if "next_index" in data:
                start = int(data.get("next_index") or 0)
            else:
                # Legacy: group_index was last completed index — resume at index+1
                start = int(data.get("group_index") or 0) + 1
            resume_cycle = int(data["cycle"]) if data.get("cycle") is not None else None
            if start < 0:
                start = 0
            return start, resume_cycle
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
        return 0, None

    async def _yield_for_priority_work(self) -> None:
        """Fair-scheduled DM service — min groups guarantee + bounded yield budget."""
        await self._fair_scheduler.yield_for_priority_work(self)

    def _persist_cycle_checkpoint(self, cycle_num: int, group_index: int, groups: list) -> None:
        import json
        import os
        from core.config import STATE_DIR

        path = os.path.join(STATE_DIR, self.slot, "cycle_checkpoint.json")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            data = {
                "cycle": cycle_num,
                "group_index": group_index,
                "next_index": group_index + 1,
                "total_groups": len(groups),
                "timestamp": time.time(),
            }
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except OSError:
            pass

    def _clear_cycle_checkpoint(self) -> None:
        import os
        from core.config import STATE_DIR

        path = os.path.join(STATE_DIR, self.slot, "cycle_checkpoint.json")
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    async def _finalize_cycle_metrics(self, groups_total: int, groups_processed: int) -> None:
        from core.cycle_metrics import cycle_metrics_store

        st = self.state
        skipped = (
            st.skipped_already_posted + st.skipped_cooldown + st.skipped_other
        )
        ended_early = self._cycle_end_reason not in ("complete",)
        metrics = cycle_metrics_store.finish_cycle(
            self.slot,
            success=st.success,
            failed=st.failed,
            skipped=skipped,
            groups_processed=groups_processed,
            ended_early=ended_early,
            end_reason=self._cycle_end_reason,
        )
        if metrics:
            st.cycle_metrics = metrics.to_dict()
        self.intel.record_cycle_flood_outcome(self._cycle_had_flood)
        await event_bus.publish(
            EventType.CYCLE_COMPLETE,
            self.slot,
            st.cycle_metrics or {},
            push_state=True,
        )
        self._clear_cycle_checkpoint()
        self._cycle_end_reason = "complete"
        self._cycle_groups_done = 0
        self._cycle_metrics_active = False

    def _sync_health_to_state(self) -> None:

        self.state.health_score = self.intel.health_score

        self.state.delay_multiplier = self.intel.delay_multiplier



    async def _on_logger_entry(self, entry: dict) -> None:

        """Route feature logs into this account's log buffer only."""

        try:

            full = entry.get("msg", "")

            if not full or full == self._last_log_msg or full in self._recent_logs:

                return

            self._last_log_msg = full

            self._recent_logs.append(full)

            self.logger.logs.append(entry)

            if len(self.logger.logs) > MAX_LOG_ENTRIES:

                self.logger.logs = self.logger.logs[-MAX_LOG_ENTRIES:]

            self.state.logs = list(self.logger.logs)

            await self._notify()

        except Exception:

            pass



    async def _notify(self) -> None:

        try:

            if self._on_state_change:

                await self._on_state_change()

        except Exception:

            pass



    async def _log(

        self,

        msg: str = "",

        level: str = "info",

        *,

        event: LogEvent | str | None = None,

        cycle: int | None = None,

        group: str | None = None,

        fields: dict | None = None,

        action: str = "",

        reason: str = "",

        delay_used: int | None = None,

    ) -> None:

        """Structured per-account log — [TIME LEVEL account cycle=N EVENT k=v ...]."""

        try:

            log_event = event if event is not None else infer_event_from_legacy(action, reason, msg)

            merged = dict(fields or {})

            if delay_used is not None:

                merged.setdefault("delay_sec", delay_used)

            if reason:

                merged.setdefault("reason", reason)

            if msg and log_event == LogEvent.GENERIC and "detail" not in merged:

                merged["detail"] = msg.strip()

            entry = build_log_entry(

                account_id=self.slot,

                event=log_event,

                level=level,

                cycle=cycle if cycle is not None else (self.state.cycle or None),

                group_id=group,

                fields=merged or None,

                action=action,

                reason=reason,

                delay_used=delay_used,

                message=msg,

            )

            full = entry["msg"]

            if full == self._last_log_msg or full in self._recent_logs:

                return

            self._last_log_msg = full

            self._recent_logs.append(full)

            self.logger.logs.append(entry)

            if len(self.logger.logs) > MAX_LOG_ENTRIES:

                self.logger.logs = self.logger.logs[-MAX_LOG_ENTRIES:]

            self.state.logs = list(self.logger.logs)

            await self._notify()

        except Exception:

            pass



    def _set_notification(self, text: str) -> None:

        self.state.notification = text



    def _flood_streak_limit(self) -> int:
        if self.intel.health_score < FLOOD_HEALTH_LOW_THRESHOLD:
            return FLOOD_STREAK_MAX_LOW_HEALTH
        return FLOOD_STREAK_MAX_HEALTHY

    def _filter_groups(self, groups: list) -> list:

        dead = self.state.invalid_groups | self.state.blocked_groups

        return [g for g in groups if g not in dead]



    async def _wait_countdown(self, seconds: int, status: str, message: str, *, log: bool = True) -> None:

        st = self.state

        st.status = status

        st.next_cycle_in = seconds

        self._set_notification(message or f"Waiting {seconds}s")

        if log and message:
            await self._log(
                "",
                level="info",
                event=LogEvent.RETRY_SCHEDULED,
                fields={"status": status, "retry_sec": seconds, "detail": message},
            )
        elif log:
            await self._log(
                "",
                level="info",
                event=LogEvent.RETRY_SCHEDULED,
                fields={"status": status, "retry_sec": seconds},
            )

        await self._notify()



        def on_tick(remaining: int) -> None:

            st.next_cycle_in = remaining

            if remaining > 0:

                self._set_notification(f"{message} — {remaining}s left")

            if remaining % 5 == 0 or remaining <= 3:

                asyncio.create_task(self._notify())



        await wait_with_countdown(seconds, st.should_continue, on_tick=on_tick)



        st.next_cycle_in = 0

        self._set_notification("")

        await self._notify()



        if st.running:

            await self._log("", level="info", event=LogEvent.CYCLE_RESUME, cycle=st.cycle)



    def _clear_flood_pause_state(self, *, heavy: bool, completed: bool = True) -> None:
        """Clear in-memory flood UI; disk join restriction only after a completed heavy pause."""
        st = self.state
        st.next_cycle_in = 0
        if heavy:
            st.heavy_rate_limit = False
            if completed:
                try:
                    from core.join_cycle import clear_join_restriction

                    clear_join_restriction(self.slot)
                except Exception:
                    pass
        if st.running and st.status == "flood_wait":
            st.status = "active"

    async def _pause_for_flood(self, pause_secs: int, headline: str, *, heavy: bool = False) -> None:

        """Sleep until rate limit clears; supports multi-hour Telegram bans."""

        st = self.state

        pause = max(0, int(pause_secs))

        if pause <= 0:

            return



        human = format_duration(pause)
        heavy_pause = heavy
        completed = False
        remaining = pause

        try:
            if heavy:
                from core.join_cycle import set_join_restriction

                set_join_restriction(self.slot, time.time() + pause)

                st.heavy_rate_limit = True

                st.status = "flood_wait"

                self._set_notification(f"🛑 Heavy rate limit — account sleeps (~{human})")

                await self._log(

                    "Heavy rate limit — account sleeps",

                    "warning",

                    action="account_sleep",

                    reason="heavy_flood",

                    delay_used=pause,

                )
                await event_bus.publish(
                    EventType.ACCOUNT_SLEEP,
                    self.slot,
                    {"seconds": pause, "heavy": True},
                )

                await self._log(

                    f"🛑 Stopping cycle early — resume in ~{human}",

                    "warning",

                    action="cycle_end",

                    reason="heavy_flood",

                )

                await self._notify()



            if pause <= 3600 and not heavy:

                await self._wait_countdown(pause, "flood_wait", f"{headline} ({human})")

                completed = True
                return



            if not heavy:

                st.status = "flood_wait"



            self._set_notification(f"{headline} — ~{human}")

            if not heavy:

                await self._log(

                    f"{headline} — sleeping ~{human}",

                    "warning",

                    action="account_sleep",

                    reason="flood_pause",

                    delay_used=pause,

                )

            await self._notify()



            remaining = pause

            while remaining > 0 and st.running:

                st.next_cycle_in = remaining

                if remaining % 600 == 0 or remaining == pause:

                    if heavy:

                        self._set_notification(

                            f"🛑 Heavy rate limit — account sleeps — ~{format_duration(remaining)} left"

                        )

                    else:

                        self._set_notification(f"{headline} — ~{format_duration(remaining)} left")

                    await self._notify()

                chunk = min(remaining, 60)

                await wait_seconds(chunk, st.should_continue)

                remaining -= chunk

            completed = remaining <= 0

        finally:
            self._clear_flood_pause_state(heavy=heavy_pause, completed=completed)
            self._set_notification("")
            try:
                await self._notify()
            except Exception:
                pass
            if st.running:
                await self._log(
                    "▶ Rate limit pause ended — resuming cycles",
                    "success",
                    action="cycle_resume",
                )



    async def _process_group_safe(
        self,
        group: str,
        msg_text: str,
        my_id: int,
        *,
        uas_action: str = "auto",
        health_score: float | None = None,
        speed_mode: str = "normal",
    ) -> str:

        """Run one atomic group operation; update this account's state only."""

        st = self.state

        delay_used: int | None = None

        try:

            if not st.running:

                return "skipped"



            skip_reason = self.intel.precheck_skip_reason(

                group,

                account_sleeping=st.heavy_rate_limit,

            )

            if skip_reason:

                labels = {

                    "account_sleeping": "account in cooldown",

                    "risky_group": "risky group (too many failures)",

                    "recently_processed": "processed recently",

                }
                if skip_reason == "recently_processed":
                    st.skipped_cooldown += 1
                else:
                    st.skipped_other += 1

                await self._log(

                    f"↷ Skipped ({labels.get(skip_reason, skip_reason)}): {group}",

                    "info",

                    group=group,

                    action="skipped",

                    reason=skip_reason,

                )

                delay_used = self._group_step_delay("skipped", skip_reason=skip_reason)
                from core.speed_optimizer import wait_with_parallel_prep

                await wait_with_parallel_prep(delay_used, st.should_continue, self._prep_next_send_async)
                # Do not refresh cooldown timestamps for safety skips. Otherwise a
                # recently_processed skip extends itself every cycle and can starve sending.
                if skip_reason not in {"recently_processed", "risky_group", "account_sleeping"}:
                    self.intel.record_touch(group)
                return "skipped"



            st.current_group = group

            await self._notify()

            hs = health_score if health_score is not None else st.health_score
            async def _run() -> object:
                return await run_group_operation(
                    self.slot,
                    lambda c: process_group(
                        c,
                        group,
                        msg_text,
                        my_id,
                        self.logger,
                        planned_action=uas_action,
                        health_score=hs,
                        speed_mode=speed_mode,
                    ),
                )

            try:
                raw = await _run()
            except Exception as e:
                if is_session_error(str(e)):
                    await self._log(
                        f"↻ Session error — retrying: {group} ({str(e)[:80]})",
                        "warning",
                        group=group,
                        action="reconnect",
                    )
                    await reconnect_client(self.slot, wait=SESSION_LOCK_RECONNECT_WAIT)
                    await asyncio.sleep(1.0)
                    raw = await _run()
                else:
                    raise

            result, meta = _parse_op_result(raw)
            detail = (meta.get("detail") or "") if meta else ""
            if result == "error" and is_session_error(detail):
                await self._log(
                    f"↻ Reconnect after: {detail[:60]} — retrying {group}",
                    "warning",
                    group=group,
                    action="reconnect",
                )
                await reconnect_client(self.slot, wait=SESSION_LOCK_RECONNECT_WAIT)
                await asyncio.sleep(1.0)
                raw = await _run()
                result, meta = _parse_op_result(raw)



            self.intel.record_result(group, result)
            if result in (
                "joined_sent",
                "pre_joined",
                "join_limited",
                "joined_new",
            ) or uas_action in ("join_then_send", "pre_join"):
                self.intel.record_join_outcome(group, result)
            if self._scheduler_ctx and result in ("joined_sent", "pre_joined"):
                self._scheduler_ctx.on_join_completed()

            self._sync_health_to_state()



            if result == "skipped":

                st.skipped_already_posted += 1

                await self._log(

                    f"↷ Skipped — our message in recent history: {group}",

                    "info",

                    group=group,

                    action="skipped",

                    reason="message_recent",

                )

            elif result == "join_limited":

                st.skipped_other += 1

                await self._log(

                    f"↷ Skipped — join limit / scheduler: {group}",

                    "info",

                    group=group,

                    action="skipped",

                    reason="join_rate_limit",

                )

            elif result == "pre_joined":

                st.skipped_other += 1
                if meta.get("new_join"):
                    self._bump_membership_after_join()

                await self._log(

                    f"🔗 Pre-joined (send deferred): {group}",

                    "info",

                    group=group,

                    action="pre_join",

                    reason="proactive_join",

                )

            elif result in ("ok", "sent"):

                self._session_lock_streak = 0
                st.flood_streak = 0

                st.success += 1
                try:
                    from core.send_stats import record_send

                    record_send(self.slot)
                except Exception:
                    pass

                st.success_list.append(group)

                await self._log(

                    f"Message sent to: {group}",

                    "success",

                    group=group,

                    action="sent",

                    reason="ok",

                )

            elif result == "joined_sent":

                self._session_lock_streak = 0
                st.flood_streak = 0
                self._bump_membership_after_join()

                st.success += 1
                try:
                    from core.send_stats import record_send

                    record_send(self.slot)
                except Exception:
                    pass

                st.success_list.append(group)

                await self._log(

                    f"Joined and message sent to: {group}",

                    "success",

                    group=group,

                    action="joined",

                    reason="joined_sent",

                )

            elif result == "invalid":

                self._session_lock_streak = 0
                st.invalid_groups.add(group)
                st.failed += 1
                st.failed_list.append({"group": group, "reason": "Invalid — removed from master"})

                try:
                    save_account_dead(self.slot, st.invalid_groups, st.blocked_groups)
                    purge = purge_invalid_from_master(group)
                    if purge.get("removed"):
                        await self._log(
                            f"🗑 Invalid username removed from master: {group} "
                            f"({purge['before']} → {purge['after']} groups)",
                            "warning",
                            group=group,
                            action="failed",
                            reason="invalid_purged",
                        )
                    else:
                        await self._log(
                            f"🗑 Invalid group skipped: {group}",
                            "warning",
                            group=group,
                            action="failed",
                            reason="invalid",
                        )
                except Exception as exc:
                    await self._log(
                        f"🗑 Invalid group {group} — save/purge failed: {exc}",
                        "error",
                        group=group,
                        action="failed",
                        reason="invalid",
                    )

            elif result == "blocked":

                st.blocked_groups.add(group)

                st.failed += 1

                st.failed_list.append({"group": group, "reason": "Admin/broadcast — removed"})

                await self._log(

                    f"🚫 Cannot post (admin/broadcast): {group}",

                    "warning",

                    group=group,

                    action="failed",

                    reason="blocked",

                )

            elif result == "flood":
                self._cycle_had_flood = True

                secs = int(meta.get("seconds", 60))

                human = format_duration(secs)

                hard_ban = secs >= FLOOD_HARD_BAN_SECONDS
                medium_ban = secs >= FLOOD_END_CYCLE_SECONDS
                api_hit = meta.get("api", "?")

                metrics_store.record_flood_wait(self.slot)
                self._timing_policy.record_flood(secs)
                st.flood_streak += 1
                st.failed += 1

                st.failed_list.append({

                    "group": group,

                    "reason": f"Rate limited ({api_hit}, ~{human})",

                })



                if hard_ban:

                    pause = _flood_pause_seconds(secs, streak=False)

                    await self._log(

                        f"🛑 Heavy rate limit on: {group} — API: {api_hit} — ~{human} wait",

                        "warning",

                        group=group,

                        action="failed",

                        reason="heavy_flood",

                    )

                    await self._pause_for_flood(

                        pause,

                        f"🛑 Heavy rate limit (~{human})",

                        heavy=True,

                    )

                    st.flood_streak = 0

                    return "flood_break"

                if medium_ban:
                    pause = self.intel.compute_medium_flood_pause(secs)
                    await self._log(
                        f"⏸ Medium rate limit ({api_hit}) ~{human} — stopping cycle to avoid long ban",
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
                if st.flood_streak < streak_limit:

                    small_wait = self.intel.small_flood_wait_seconds(secs)

                    await self._log(

                        f"⚠ Rate limited on: {group} — waiting ~{small_wait}s then next group",

                        "warning",

                        group=group,

                        action="failed",

                        reason="small_flood",

                        delay_used=small_wait,

                    )

                    await wait_seconds(small_wait, st.should_continue)

                else:

                    pause = _flood_pause_seconds(secs, streak=True)

                    await self._log(

                        f"⏸ {st.flood_streak} rate limits in a row — pausing {format_duration(pause)}",

                        "warning",

                        group=group,

                        action="cycle_end",

                        reason="flood_streak",

                        delay_used=pause,

                    )

                    await self._pause_for_flood(

                        pause,

                        f"⏸ Rate limited — pause {format_duration(pause)}",

                    )

                    st.flood_streak = 0

                    return "flood_break"

            elif result == "cant_write":

                st.blocked_groups.add(group)

                st.failed += 1

                st.failed_list.append({"group": group, "reason": "Cannot post — removed"})

                await self._log(

                    f"🚫 Cannot post after join: {group}",

                    "warning",

                    group=group,

                    action="failed",

                    reason="cant_write",

                )

                self._session_lock_streak = 0

            elif result == "error" and (
                meta.get("session") or is_session_error(str(meta.get("detail") or ""))
            ):

                self._session_lock_streak += 1

                st.failed += 1

                err_detail = (meta.get("detail") or "database is locked")[:200]

                st.failed_list.append({"group": group, "reason": err_detail})

                await self._log(

                    f"✗ Session busy on: {group} — {err_detail[:80]} (cooldown {SESSION_LOCK_GROUP_COOLDOWN}s)",

                    "warning",

                    group=group,

                    action="failed",

                    reason="session_locked",

                )

                await reconnect_client(self.slot, wait=SESSION_LOCK_RECONNECT_WAIT)

                await wait_seconds(SESSION_LOCK_GROUP_COOLDOWN, st.should_continue)

                if self._session_lock_streak >= SESSION_LOCK_STREAK_END_CYCLE:

                    await self._log(

                        f"⏸ {self._session_lock_streak} session lock errors — pausing "

                        f"{SESSION_LOCK_STREAK_PAUSE}s (SQLite recovery)",

                        "warning",

                        action="cycle_end",

                        reason="session_lock_streak",

                        delay_used=SESSION_LOCK_STREAK_PAUSE,

                    )

                    self._session_lock_streak = 0

                    await wait_seconds(SESSION_LOCK_STREAK_PAUSE, st.should_continue)

                    return "session_break"

            else:

                self._session_lock_streak = 0

                st.failed += 1

                err_detail = meta.get("detail") if meta else ""

                reason = err_detail or str(result)

                st.failed_list.append({"group": group, "reason": reason[:200]})

                await self._log(

                    f"✗ Failed on: {group} — {reason} (retry next cycle)",

                    "error",

                    group=group,

                    action="failed",

                    reason=reason[:120],

                )



            try:
                save_account_dead(self.slot, set(), st.blocked_groups)
            except Exception:
                pass

            if result in ("skipped", "join_limited"):
                delay_used = self._group_step_delay(
                    "skipped",
                    skip_reason=(
                        "join_rate_limit"
                        if result == "join_limited"
                        else "message_recent"
                    ),
                )
            else:
                delay_used = self._policy_scaled_send_delay()

            from core.speed_optimizer import wait_with_parallel_prep

            await wait_with_parallel_prep(delay_used, st.should_continue, self._prep_next_send_async)

            return result



        except Exception as e:

            self.intel.record_result(group, "error")

            self._sync_health_to_state()

            if is_session_error(str(e)):
                try:
                    await reconnect_client(self.slot)
                except Exception:
                    pass

            await self._log(

                f"✗ Error on: {group} — {e}",

                "error",

                group=group,

                action="failed",

                reason="exception",

            )

            return "error"

        finally:

            st.current_group = ""

            await self._notify()



    async def _execute_cycle(self) -> bool:

        st = self.state

        if not st.running:

            return False

        if not self.state.account_info or not self.state.account_info.get("phone"):
            st.running = False
            return False

        from core.telegram_client import is_login_exclusive

        if is_login_exclusive(self.slot):
            st.running = False
            return False

        from core.join_cycle import restriction_remaining_seconds

        restr_wait = restriction_remaining_seconds(self.slot)
        if restr_wait > 0:
            await self._wait_countdown(
                min(restr_wait, 3600),
                "flood_wait",
                f"🛑 Account restricted — waiting {format_duration(restr_wait)}",
            )
            return False

        if st.heavy_rate_limit:

            still_wait = self.intel.compute_still_limited_wait()
            await self._wait_countdown(
                still_wait, "flood_wait", "🛑 Account still rate-limited — waiting",
            )

            return False



        st.status = "active"

        self._set_notification("")

        await self._notify()



        try:

            health = None
            client = None
            for attempt in range(4):
                try:
                    client = await get_client(self.slot)
                    health = await check_account_health(client, self.logger)
                    if health != "error" or attempt >= 3:
                        break
                    await self._log(
                        f"Health check retry ({attempt + 1}/3) — session busy",
                        "warning",
                        action="health_retry",
                    )
                    await reconnect_client(self.slot, wait=5.0)
                    await asyncio.sleep(1.0 * (attempt + 1))
                except Exception as exc:
                    if is_session_error(str(exc)) and attempt < 3:
                        await reconnect_client(self.slot, wait=5.0)
                        await asyncio.sleep(1.0 * (attempt + 1))
                        continue
                    if attempt >= 3:
                        recovery_wait = self.intel.compute_error_recovery_wait()
                        await self._wait_countdown(
                            recovery_wait, "recovering",
                            f"Connection failed — retry in {recovery_wait}s",
                        )
                        return False
                    await reconnect_client(self.slot, wait=5.0)
                    await asyncio.sleep(1.0 * (attempt + 1))

            if client is None or health is None:
                recovery_wait = self.intel.compute_error_recovery_wait()
                await self._wait_countdown(
                    recovery_wait, "recovering",
                    f"Connection failed — retry in {recovery_wait}s",
                )
                return False
            flood_secs = 0
            if isinstance(health, tuple):
                flood_secs = int(health[1]) if len(health) > 1 else 0
                health = health[0]

            if health == "not_authorized":

                await self._wait_countdown(

                    NOT_AUTH_RETRY_SECONDS, "recovering",

                    f"Not logged in — retry in {NOT_AUTH_RETRY_SECONDS}s",

                )

                return False



            if health == "flood_banned":
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
                return False



            if health != "ok":

                recovery_wait = self.intel.compute_error_recovery_wait()
                await self._wait_countdown(
                    recovery_wait, "recovering",
                    f"Health check failed — retry in {recovery_wait}s",
                )

                return False



            await self._log("", level="info", event=LogEvent.TELEGRAM_CONNECTED)



            try:

                me = await client.get_me()

                my_id = me.id

            except Exception:

                recovery_wait = self.intel.compute_error_recovery_wait()
                await self._wait_countdown(
                    recovery_wait, "recovering",
                    f"get_me failed — retry in {recovery_wait}s",
                )

                return False



            master = load_master_groups()
            try:
                disk_invalid, disk_blocked = load_account_dead(self.slot)
                if disk_invalid != self.state.invalid_groups:
                    self.state.invalid_groups = disk_invalid
                if disk_blocked != self.state.blocked_groups:
                    self.state.blocked_groups = disk_blocked
            except Exception:
                pass
            groups = self._filter_groups(groups_readonly_snapshot_for_slot(self.slot))

            st.my_groups = list(groups)

            self._sync_health_to_state()

            start_index, resume_cycle = self._load_cycle_checkpoint(len(groups))
            if resume_cycle is not None:
                st.cycle = resume_cycle
            else:
                st.cycle += 1
            msg_text = prepare_cycle_message(self.slot, st.cycle)
            preview = (msg_text.split("\n")[0] or "")[:120]
            st.cycle_message_preview = preview

            from core.execution_policy import compute_execution_policy

            timing = self._timing_policy.snapshot()
            self._execution_policy = compute_execution_policy(
                self.slot,
                health_score=st.health_score,
                heavy_rate_limit=st.heavy_rate_limit,
                flood_streak=st.flood_streak,
                fleet_pressure=timing.fleet_pressure,
                fleet_delay_multiplier=timing.delay_multiplier,
                recently_flooded=timing.recently_flooded,
            )
            self._speed_profile = self._build_speed_profile()
            speed_mode = self._speed_profile.mode if self._speed_profile else "normal"
            groups = self.intel.prioritize_groups(groups, speed_mode=speed_mode)
            st.my_groups = list(groups)
            from core.unified_scheduler import build_scheduler_context

            self._scheduler_ctx = build_scheduler_context(
                self.slot,
                health_score=st.health_score,
                success_rate=self._cycle_success_rate() or self._avg_cycle_success_rate(),
                flood_streak=st.flood_streak,
                cycles_without_flood=self.intel.cycles_without_flood,
                fleet_pressure=self._execution_policy.fleet_pressure,
                unhealthy=self._execution_policy.unhealthy,
                heavy_rate_limit=st.heavy_rate_limit,
                speed_mode=self._speed_profile.mode,
            )
            st.execution_policy = self._execution_policy.to_dict()
            st.speed_profile = self._speed_profile.to_dict()
            policy_dict = dict(st.execution_policy or {})
            policy_dict["scheduler"] = self._scheduler_ctx.to_dict()
            st.execution_policy = policy_dict
            self._fair_scheduler.begin_cycle(self._execution_policy)
            self._cycle_had_flood = False
            self._next_send_delay = None

            part = partition_summary(self.slot, master)

            await self._log(
                "",
                level="info",
                event=LogEvent.CYCLE_START,
                cycle=st.cycle,
                fields={
                    "groups": len(groups),
                    "total": part["total_master"],
                    "slice_index": part["slot_index"],
                    "account_count": part["account_count"],
                    "health_pct": int(st.health_score),
                    "speed_mode": self._speed_profile.mode,
                    "message_rewritten": MESSAGE_REWRITE_ENABLED,
                },
            )
            if MESSAGE_REWRITE_ENABLED:
                await self._log(
                    "",
                    level="info",
                    event=LogEvent.MSG_VARIANT_READY,
                    cycle=st.cycle,
                )

            self._set_notification(f"▶ Cycle {st.cycle} started — {len(groups)} groups")

            await self._notify()



            if not groups:

                await self._log(
                    "",
                    level="warning",
                    event=LogEvent.GROUP_SOURCE_EMPTY,
                    cycle=st.cycle,
                    fields={
                        "retry_sec": NO_GROUPS_RETRY_SECONDS,
                        "action_required": "upload_groups_list",
                    },
                )

                await self._wait_countdown(
                    NO_GROUPS_RETRY_SECONDS,
                    "recovering",
                    "",
                    log=False,
                )

                return False



            st.success = 0

            st.failed = 0

            st.skipped_already_posted = 0

            st.skipped_cooldown = 0

            st.skipped_other = 0

            st.success_list = []

            st.failed_list = []

            st.flood_streak = 0

            action_count = 0

            groups_since_break = 0

            from core.speed_optimizer import compute_batch_break_seconds, next_batch_break_after

            break_at = (
                next_batch_break_after(self._speed_profile)
                if self._speed_profile
                else self.intel.next_batch_break_after(0)
            )
            self._cycle_context = {"groups": groups, "msg_text": msg_text, "my_id": my_id, "index": 0}

            self._cycle_end_reason = "complete"
            self._cycle_groups_done = 0

            from core.cycle_metrics import cycle_metrics_store

            cycle_metrics_store.start_cycle(self.slot, st.cycle, len(groups))
            self._cycle_metrics_active = True

            for gi, group in enumerate(groups):
                if gi < start_index:
                    continue

                if self._cycle_context is not None:
                    self._cycle_context["index"] = gi

                if self._fair_scheduler.cycle_wall_exceeded():
                    self._cycle_end_reason = "cycle_wall_limit"
                    await self._log(
                        "⏱ Cycle wall time reached — finishing early (stall prevention)",
                        "warning",
                        action="cycle_end",
                        reason="cycle_wall_limit",
                    )
                    break

                if not st.running:

                    self._cycle_end_reason = "stopped"
                    break



                from core.unified_scheduler import Action, decide

                uas_action = "auto"
                if self._scheduler_ctx:
                    sched_dec = decide(group, self._scheduler_ctx, self.intel)
                    if sched_dec.action == Action.SKIP:
                        if sched_dec.reason == "recently_processed":
                            st.skipped_cooldown += 1
                        else:
                            st.skipped_other += 1
                        await self._log(
                            f"↷ Scheduler skip ({sched_dec.reason}): {group}",
                            "info",
                            group=group,
                            action="skipped",
                            reason=sched_dec.reason,
                        )
                        self._cycle_groups_done = gi + 1
                        self._fair_scheduler.on_group_completed()
                        self._scheduler_ctx.on_group_step()
                        # Scheduler skips do not attempt Telegram work. Touching them would
                        # continually renew the recent-processing cooldown and prevent sends.
                        if sched_dec.reason not in {"recently_processed", "risky_group", "account_sleeping"}:
                            self.intel.record_touch(group)
                        st.last_activity_at = time.time()
                        groups_since_break += 1
                        skip_wait = self._group_step_delay(
                            "skipped", skip_reason=sched_dec.reason
                        )
                        if skip_wait > 0:
                            from core.speed_optimizer import wait_with_parallel_prep

                            await wait_with_parallel_prep(
                                skip_wait,
                                st.should_continue,
                                self._prep_next_send_async,
                            )
                        if groups_since_break >= break_at and st.running:
                            break_secs = (
                                compute_batch_break_seconds(self._speed_profile)
                                if self._speed_profile
                                else self.intel.compute_batch_break_seconds()
                            )
                            await self._log(
                                f"☕ Human break — resting {break_secs}s after {groups_since_break} groups",
                                "info",
                                action="batch_break",
                                reason="human_pattern",
                                delay_used=break_secs,
                            )
                            await wait_with_parallel_prep(
                                break_secs, st.should_continue, self._prep_next_send_async
                            )
                            groups_since_break = 0
                            break_at = (
                                next_batch_break_after(self._speed_profile)
                                if self._speed_profile
                                else self.intel.next_batch_break_after(groups_since_break)
                            )
                        await self._yield_for_priority_work()
                        continue
                    uas_action = sched_dec.action.value

                result = await message_router.dispatch_inline(
                    QueueTask(
                        account_id=self.slot,
                        task_type=TaskType.GROUP_POST,
                        payload={
                            "group": group,
                            "message": msg_text,
                            "uas_action": uas_action,
                            "health_score": st.health_score,
                            "speed_mode": self._speed_profile.mode if self._speed_profile else "normal",
                        },
                    )
                )

                if self._scheduler_ctx:
                    self._scheduler_ctx.on_group_step()

                self._cycle_groups_done = gi + 1
                self._fair_scheduler.on_group_completed()
                st.last_activity_at = time.time()

                if gi > 0 and gi % 10 == 0:
                    self._persist_cycle_checkpoint(st.cycle, gi, groups)

                if result in ("flood_break", "session_break"):
                    self._cycle_end_reason = result
                    break



                code, _ = _parse_op_result(result) if isinstance(result, tuple) else (result, {})

                if code != "skipped":

                    action_count += 1



                groups_since_break += 1

                if groups_since_break >= break_at and st.running:

                    break_secs = (
                        compute_batch_break_seconds(self._speed_profile)
                        if self._speed_profile
                        else self.intel.compute_batch_break_seconds()
                    )

                    await self._log(

                        f"☕ Human break — resting {break_secs}s after {groups_since_break} groups",

                        "info",

                        action="batch_break",

                        reason="human_pattern",

                        delay_used=break_secs,

                    )

                    await wait_with_parallel_prep(
                        break_secs, st.should_continue, self._prep_next_send_async
                    )

                    groups_since_break = 0

                    break_at = (
                        next_batch_break_after(self._speed_profile)
                        if self._speed_profile
                        else self.intel.next_batch_break_after(groups_since_break)
                    )

                await self._yield_for_priority_work()



            st.active_groups = action_count

            await self._finalize_cycle_metrics(len(groups), self._cycle_groups_done)

            try:
                from core.groups_store import save_group_health_snapshot

                save_group_health_snapshot(self.slot)
            except Exception:
                pass

            await self._notify()



            if action_count == 0:

                await self._log(

                    "↷ Cycle done — nothing to post (all skipped or pre-filtered)",

                    action="cycle_end",

                )

            else:

                total = st.success + st.failed

                rate = round(st.success / total * 100, 1) if total > 0 else 0

                await self._log(

                    f"✓ Cycle {st.cycle} finished — posted: {st.success} | failed: {st.failed} ({rate}%)"
                    + (
                        f" · {st.cycle_metrics.get('duration_seconds', 0)}s"
                        f" · {st.cycle_metrics.get('groups_per_second', 0)}/s"
                        if st.cycle_metrics
                        else ""
                    ),

                    "success",

                    action="cycle_end",

                    reason=f"success_rate_{rate}",

                )

            return self._cycle_end_reason in ("complete", "cycle_wall_limit")

            await self._log(f"Cycle error (recovered): {e}", "error", action="cycle_error")
            self._cycle_end_reason = "error"
            if self._cycle_metrics_active:
                await self._finalize_cycle_metrics(
                    len(st.my_groups) if st.my_groups else self._cycle_groups_done,
                    self._cycle_groups_done,
                )

            recovery_wait = self.intel.compute_error_recovery_wait()
            await self._wait_countdown(
                recovery_wait, "recovering",
                f"Error — retry in {recovery_wait}s",
            )

            return False

        finally:

            st.current_group = ""

            await self._notify()



    async def _run_forever(self) -> None:

        st = self.state

        st.status = "active"

        if not self._announced_start:
            st.cycle = 0



        if not self._announced_start:

            mode = "one cycle (test)" if self._one_shot else "24/7 until STOP"

            await self._log(

                f"🟢 Worker started — smart mode {mode}",

                "success",

                action="worker_start",

            )

            self._announced_start = True

        from core.telegram_client import set_login_exclusive

        set_login_exclusive(self.slot, False)

        await self.ensure_queue_processor()

        while st.running:
            from core.telegram_client import is_login_exclusive

            if is_login_exclusive(self.slot):
                st.running = False
                break

            st.last_activity_at = time.time()

            try:
                async with self._cycle_lock:
                    apply_delay = await self._execute_cycle()

            except Exception as e:

                await self._log(f"Unexpected error (recovered): {e}", "error", action="cycle_error")

                apply_delay = False

                recovery_wait = self.intel.compute_error_recovery_wait()
                await self._wait_countdown(
                    recovery_wait, "recovering",
                    f"Error — retry in {recovery_wait}s",
                )

            st.last_activity_at = time.time()



            if not st.running:

                break



            if self._pending_joined_scan:
                self._pending_joined_scan = False
                await self._scan_joined_stats_now()

            if self._one_shot:

                st.running = False

                break



            if apply_delay:

                cycle_delay = self._policy_scaled_cycle_delay()

                total = st.success + st.failed

                rate = round(st.success / total * 100, 1) if total > 0 else 0

                await self._wait_countdown(

                    cycle_delay, "waiting",

                    f"⏳ Next cycle in {cycle_delay}s (last: ✓ {st.success} ✗ {st.failed} {rate}%)",

                )



        if self._one_shot:

            self._one_shot = False

            try:

                from core.worker_persistence import mark_stopped

                mark_stopped(self.slot)

            except Exception:

                pass



        st.status = "stopped"

        st.current_group = ""

        st.next_cycle_in = 0

        st.heavy_rate_limit = False

        self._set_notification("")

        self._announced_start = False

        self._last_log_msg = ""

        await self._log("", level="info", event=LogEvent.WORKER_STOP)

        await self._notify()

        try:
            from core.telegram_client import release_session

            await release_session(self.slot, wait=0.25)
        except Exception:
            pass



    def _task_done_callback(self, task: asyncio.Task) -> None:

        if self.state.task is not task:

            return

        exc: BaseException | None = None
        try:

            exc = task.exception()

        except asyncio.CancelledError:

            return

        except Exception as callback_exc:

            exc = callback_exc

        if exc is not None:

            asyncio.create_task(

                self._log(f"Worker crashed — auto-restarting: {exc}", "error", action="crash")

            )



        if self.state.running:
            if self._manager is not None:
                asyncio.create_task(self._manager.handle_worker_crash(self.slot, exc))
            else:
                asyncio.create_task(self._restart_after_crash())



    async def _restart_after_crash(self) -> None:

        if not self.state.running:

            return

        try:
            from core.system_lifecycle import log_system_event

            log_system_event(
                "Worker task crashed — scheduling restart",
                reason="crash",
                detail=self.slot,
            )
        except Exception:
            pass

        await self._wait_countdown(

            CRASH_RESTART_SECONDS, "recovering",

            f"♻ Auto-restart in {CRASH_RESTART_SECONDS}s",

        )

        if self.state.running:

            self._launch_task()



    def _launch_task(self) -> None:

        self._cancel_task()

        self.state.task = asyncio.create_task(self._run_forever())

        self.state.task.add_done_callback(self._task_done_callback)



    def start(self, one_shot: bool = False) -> bool:

        with self._start_lock:
            from core.telegram_client import is_login_exclusive

            if is_login_exclusive(self.slot):
                return False

            t = self.state.task

            if self.state.running and t is not None and not t.done():

                return False

            self._cancel_task()

            self._one_shot = one_shot
            self._clear_flood_pause_state(heavy=True)
            self.state.heavy_rate_limit = False

            self.state.running = True

            self._launch_task()

            return True



    def _cancel_task(self) -> None:

        task = self.state.task

        if task is not None and not task.done():

            task.cancel()



    def stop(self) -> None:

        self.state.running = False
        self._one_shot = False
        st = self.state
        st.next_cycle_in = 0
        st.heavy_rate_limit = False
        if st.status == "flood_wait":
            st.status = "stopped"

        self._announced_start = False

        self._last_log_msg = ""

        self._recent_logs.clear()

        task = self.state.task

        if task is not None and not task.done():

            task.cancel()

    def reset_after_logout(self) -> None:
        """Hard reset UI/worker state after logout — no zombie running/sleep flags."""
        self.stop()
        self.state.account_info = None
        self.state.status = "stopped"
        self.state.current_group = ""
        self.state.next_cycle_in = 0
        self.state.heavy_rate_limit = False
        self.state.notification = ""
        self.state.running = False
        self.state.task = None
        self._pending_joined_scan = False



    async def clear_logs(self) -> None:

        """Clear log buffer only — does not affect success/failed counts or workers."""

        self.logger.logs.clear()

        self.state.logs = []

        self._recent_logs.clear()

        self._last_log_msg = ""

        await self._notify()



    async def refresh_info(self, *, preserve_on_error: bool = True) -> dict | None:
        """
        Refresh name/phone from Telethon session.
        Does NOT clear login on transient errors (database locked, reload, disconnect).
        """
        from core.telegram_client import is_login_exclusive

        cached = self.state.account_info or load_account_info(self.slot)
        if is_login_exclusive(self.slot):
            return cached

        try:
            client = await get_client(self.slot)

            if await client.is_user_authorized():
                me = await client.get_me()
                from core.account_info_store import build_info_from_me

                info = build_info_from_me(me, cached)
                self.state.account_info = info
                save_account_info(self.slot, info)
                return info

            # Session file exists but Telegram says not authorized — real logout
            self.state.account_info = None
            clear_account_info(self.slot)
            return None

        except Exception:
            if preserve_on_error and cached:
                self.state.account_info = cached
                return cached
            if preserve_on_error and self.state.account_info:
                return self.state.account_info
            return None

    def request_joined_scan(self) -> None:
        """Queue a dialog scan (safe while worker is running)."""
        self._pending_joined_scan = True

    def _bump_membership_after_join(self) -> None:
        """Optimistic UI bump + schedule full Telegram rescan after a new join."""
        base = self.state.account_info or load_account_info(self.slot)
        if not base:
            return
        if base.get("joined_total") is not None:
            groups = int(base.get("joined_groups") or 0) + 1
            total = int(base.get("joined_total") or 0) + 1
            from core.subscription_accounts import enrich_account_info

            info = enrich_account_info(
                self.slot,
                {**base, "joined_groups": groups, "joined_total": total},
            )
            self.state.account_info = info
            save_account_info(self.slot, info)
            asyncio.create_task(self._push_membership_ws(info))
        from core.joined_membership import refresh_membership_after_join

        asyncio.create_task(
            refresh_membership_after_join(
                self.slot,
                self,
                push_state=self._on_state_change,
            )
        )

    async def _push_membership_ws(self, info: dict) -> None:
        from core.joined_membership import push_membership_update

        try:
            await push_membership_update(self.slot, info)
        except Exception:
            pass

    async def _scan_joined_stats_now(self) -> dict | None:
        """Count Telegram groups/channels between cycles (non-blocking when possible)."""
        from core.joined_membership import refresh_membership

        base = self.state.account_info or load_account_info(self.slot)
        if not base or not base.get("phone"):
            return None

        if self._session_lock_streak >= 2:
            self._pending_joined_scan = True
            await self._log(
                "📊 On Telegram scan deferred — session busy (will retry between cycles)",
                "warning",
                action="joined_scan",
            )
            return base

        await self._log(
            "📊 Scanning On Telegram membership…",
            "info",
            action="joined_scan",
        )
        info = await refresh_membership(
            self.slot,
            self,
            reason="worker_cycle",
            notify=True,
            push_state=self._on_state_change,
        )
        if info and info.get("joined_total") is not None:
            await self._log(
                f"📊 On Telegram: {info['joined_total']} total "
                f"({info.get('joined_groups', 0)} groups, "
                f"{info.get('joined_channels', 0)} channels)",
                "success",
                action="joined_scan",
            )
        return info

    async def refresh_joined_stats(self) -> dict | None:
        """Refresh On Telegram counts (string session when worker is running)."""
        from core.joined_membership import refresh_membership

        base = self.state.account_info or load_account_info(self.slot)
        if not base or not base.get("phone"):
            return None
        return await refresh_membership(
            self.slot,
            self,
            reason="manual",
            notify=True,
            push_state=self._on_state_change,
        )

    async def ensure_queue_processor(self) -> None:
        """Start per-account queue consumer (isolated from other accounts)."""
        if self._queue_task is not None and not self._queue_task.done():
            return
        self._queue_active = True
        self._queue_task = asyncio.create_task(self._queue_processor_loop())

    async def stop_queue_processor(self) -> None:
        self._queue_active = False
        if self._queue_task is not None and not self._queue_task.done():
            self._queue_task.cancel()
            try:
                await self._queue_task
            except asyncio.CancelledError:
                pass
        self._queue_task = None

    async def _queue_processor_loop(self) -> None:
        """Single consumer for this account's queue — no cross-account tasks."""
        queue = self._queue
        while self._queue_active:
            task = await queue.get(timeout=1.0)
            if task is None:
                continue
            queue.set_processing(True)
            try:
                result = await self._handle_queue_task(task)
                if task.wait_result:
                    queue.complete_task(task.task_id, result)
            except Exception as exc:
                metrics_store.record_task_fail(self.slot, error=str(exc)[:200])
                if task.wait_result:
                    queue.complete_task(task.task_id, error=exc)
                await event_bus.publish(
                    EventType.ACCOUNT_ERROR,
                    self.slot,
                    {"task": task.to_dict(), "error": str(exc)[:200]},
                    push_state=True,
                )
                await retry_manager.schedule_retry_from_exception(self.slot, task, exc)
            else:
                metrics_store.record_task_ok(self.slot)
                if task.task_type == TaskType.GROUP_POST and isinstance(result, str):
                    if result == "sent":
                        metrics_store.record_sent(self.slot)
                    else:
                        metrics_store.record_failed(self.slot, error=result)
                        clf = classify_task_result(result)
                        if clf and clf.retryable:
                            await retry_manager.schedule_retry(
                                self.slot,
                                task,
                                reason=clf.reason,
                                flood_seconds=clf.flood_seconds,
                                network=clf.network,
                                classification=clf,
                            )
            finally:
                queue.set_processing(False)
                queue.task_done()
                await event_bus.publish(
                    EventType.QUEUE_UPDATE,
                    self.slot,
                    queue.status_dict(),
                    push_state=True,
                )

    async def _handle_queue_task(self, task: QueueTask):
        if task.account_id != self.slot:
            raise ValueError(f"Wrong account on queue: {task.account_id} != {self.slot}")

        if task.task_type == TaskType.RUN_CYCLE:
            if self._cycle_lock.locked():
                await self._log(
                    "↷ Cycle already running — queued RUN_CYCLE ignored",
                    "warning",
                    action="cycle_skip",
                    reason="cycle_lock_held",
                )
                return "cycle_busy"
            async with self._cycle_lock:
                return await self._execute_cycle()

        if task.task_type == TaskType.GROUP_POST:
            async with self._execution_gate:
                group = task.payload.get("group", "")
                msg_text = task.payload.get("message")
                if not msg_text:
                    msg_text, _ = prepare_cycle_message(
                        self.slot, rewrite_enabled=MESSAGE_REWRITE_ENABLED
                    )
                client = await get_client(self.slot)
                my_id = (await client.get_me()).id
                result = await self._process_group_safe(
                    group,
                    msg_text,
                    my_id,
                    uas_action=task.payload.get("uas_action", "auto"),
                    health_score=task.payload.get("health_score"),
                    speed_mode=task.payload.get("speed_mode", "normal"),
                )
            await event_bus.publish(
                EventType.MESSAGE_SENT,
                self.slot,
                {"group": group, "result": result},
            )
            return result

        if task.task_type == TaskType.DM_SEND:
            from services import dm_inbox_service

            async with self._execution_gate:
                result = await dm_inbox_service.run_dm_send(
                    self.slot,
                    int(task.payload["user_id"]),
                    str(task.payload.get("text", "")),
                )
            await event_bus.publish(
                EventType.MESSAGE_SENT,
                self.slot,
                {
                    "user_id": task.payload.get("user_id"),
                    "channel": "dm",
                },
            )
            return result

        if task.task_type == TaskType.JOIN_GROUP:
            from features.group_operation import _join

            group = task.payload.get("group", "")

            async def _join_op(c):
                return await _join(c, group)

            async with self._execution_gate:
                return await run_group_operation(self.slot, _join_op)

        if task.task_type == TaskType.RETRY:
            orig_type = TaskType(task.payload["original_type"])
            retry_task = QueueTask(
                account_id=self.slot,
                task_type=orig_type,
                payload=dict(task.payload.get("original_payload") or {}),
                retry_count=task.retry_count,
                wait_result=task.wait_result,
                priority=task.priority,
            )
            return await self._handle_queue_task(retry_task)

        raise ValueError(f"Unknown task type: {task.task_type}")



