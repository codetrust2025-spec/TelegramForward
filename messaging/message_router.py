"""Central message router — all outgoing work is validated and queued per account."""

from __future__ import annotations

from typing import Any

from core.account_logging import account_log
from core.config import ACCOUNTS
from core.observability.account_metrics import metrics_store
from events.event_bus import event_bus
from events.event_types import EventType
from messaging.account_queue import AccountQueue, QueueBackpressureError
from messaging.task_types import QueueTask, TaskType


class MessageRouter:
    """
    UI → API → MessageRouter → per-account Queue → Worker.

    Validates account_id on every route; never mixes accounts.
    """

    def _validate(self, account_id: str) -> None:
        if account_id not in ACCOUNTS:
            raise ValueError(f"Invalid account_id: {account_id}")

    async def _ensure_processor(self, account_id: str) -> None:
        from services.account_manager import manager

        await manager.get_runtime(account_id).worker.ensure_queue_processor()

    def _runtime_queue(self, account_id: str) -> AccountQueue:
        from services.account_manager import manager

        return manager.get_runtime(account_id).queue

    async def route(self, task: QueueTask) -> str:
        self._validate(task.account_id)
        await self._ensure_processor(task.account_id)
        queue = self._runtime_queue(task.account_id)
        account_log(
            task.account_id,
            f"Routing {task.task_type.value} → queue (wait={task.wait_result})",
        )
        try:
            await queue.put(task)
        except QueueBackpressureError as e:
            metrics_store.record_queue_rejected(task.account_id)
            await event_bus.publish(
                EventType.QUEUE_OVERFLOW,
                task.account_id,
                {"depth": e.depth, "max_size": e.max_size, "task_type": task.task_type.value},
                push_state=True,
            )
            raise
        return task.task_id

    async def route_and_wait(self, task: QueueTask, timeout: float = 300.0) -> Any:
        task.wait_result = True
        await self.route(task)
        queue = self._runtime_queue(task.account_id)
        return await queue.wait_for_task(task, timeout=timeout)

    async def enqueue_group_post(
        self,
        account_id: str,
        group: str,
        *,
        message: str | None = None,
        wait: bool = False,
    ) -> str | Any:
        task = QueueTask(
            account_id=account_id,
            task_type=TaskType.GROUP_POST,
            payload={"group": group, "message": message},
            wait_result=wait,
        )
        if wait:
            return await self.route_and_wait(task)
        return await self.route(task)

    async def enqueue_dm_send(
        self,
        account_id: str,
        user_id: int,
        text: str,
        *,
        wait: bool = True,
    ) -> Any:
        task = QueueTask(
            account_id=account_id,
            task_type=TaskType.DM_SEND,
            payload={"user_id": int(user_id), "text": str(text)},
            wait_result=wait,
        )
        if wait:
            return await self.route_and_wait(task)
        return await self.route(task)

    async def enqueue_join_group(
        self,
        account_id: str,
        group: str,
        *,
        wait: bool = False,
    ) -> str | Any:
        task = QueueTask(
            account_id=account_id,
            task_type=TaskType.JOIN_GROUP,
            payload={"group": group},
            wait_result=wait,
        )
        if wait:
            return await self.route_and_wait(task)
        return await self.route(task)

    async def enqueue_cycle(self, account_id: str) -> str:
        task = QueueTask(account_id=account_id, task_type=TaskType.RUN_CYCLE, payload={})
        return await self.route(task)

    async def dispatch_inline(self, task: QueueTask) -> Any:
        """
        Execute on the account worker without re-queuing (avoids deadlock during RUN_CYCLE).
        Still validates account_id and logs routing.
        """
        self._validate(task.account_id)
        account_log(
            task.account_id,
            f"Inline dispatch {task.task_type.value}",
        )
        from services.account_manager import manager

        w = manager.get_runtime(task.account_id).worker
        return await w._handle_queue_task(task)


message_router = MessageRouter()
