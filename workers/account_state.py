"""Mutable state for ONE account only — never shared between accounts."""

from dataclasses import dataclass, field
from typing import Set


@dataclass
class AccountState:
    slot: str
    running: bool = False
    task: object | None = None  # asyncio.Task
    cycle: int = 0
    success: int = 0
    failed: int = 0
    skipped_already_posted: int = 0  # our message still in last 3 (this cycle)
    skipped_cooldown: int = 0  # processed within 30 min (this cycle)
    skipped_other: int = 0  # risky, join limit, account sleep, etc. (this cycle)
    current_group: str = ""
    success_list: list = field(default_factory=list)
    failed_list: list = field(default_factory=list)
    logs: list = field(default_factory=list)
    active_groups: int = 0
    status: str = "stopped"  # active | waiting | recovering | flood_wait | stopped
    my_groups: list = field(default_factory=list)
    next_cycle_in: int = 0
    notification: str = ""
    invalid_groups: Set[str] = field(default_factory=set)
    blocked_groups: Set[str] = field(default_factory=set)
    account_info: dict | None = None
    flood_streak: int = 0  # consecutive rate-limits in current cycle
    heavy_rate_limit: bool = False  # True during long Telegram FloodWait sleep
    health_score: float = 100.0
    delay_multiplier: float = 1.0
    cycle_message_preview: str = ""
    last_activity_at: float = 0.0  # watchdog — unix time of last cycle progress
    cycle_metrics: dict | None = None  # latest cycle run metrics snapshot
    execution_policy: dict | None = None  # adaptive policy snapshot
    speed_profile: dict | None = None  # SpeedProfile snapshot for UI

    def to_dict(self) -> dict:
        try:
            from core.send_stats import count_24h

            messages_sent_24h = count_24h(self.slot)
        except Exception:
            messages_sent_24h = 0
        return {
            "running": self.running,
            "cycle": self.cycle,
            "success": self.success,
            "failed": self.failed,
            "skipped_already_posted": self.skipped_already_posted,
            "skipped_cooldown": self.skipped_cooldown,
            "skipped_other": self.skipped_other,
            "skipped_total": (
                self.skipped_already_posted + self.skipped_cooldown + self.skipped_other
            ),
            "messages_sent_24h": messages_sent_24h,
            "current_group": self.current_group,
            "success_list": list(self.success_list),
            "failed_list": list(self.failed_list),
            "logs": list(self.logs[-100:]),
            "active_groups": self.active_groups,
            "status": self.status,
            "my_groups": list(self.my_groups),
            "next_cycle_in": self.next_cycle_in,
            "notification": self.notification,
            "heavy_rate_limit": self.heavy_rate_limit,
            "health_score": self.health_score,
            "delay_multiplier": self.delay_multiplier,
            "cycle_message_preview": self.cycle_message_preview,
            "cycle_metrics": dict(self.cycle_metrics) if self.cycle_metrics else None,
            "execution_policy": dict(self.execution_policy) if self.execution_policy else None,
            "speed_profile": dict(self.speed_profile) if self.speed_profile else None,
        }

    def should_continue(self) -> bool:
        return self.running
