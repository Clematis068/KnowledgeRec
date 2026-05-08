"""基于 Redis List 的轻量消息队列。

设计要点:
- LPUSH 入队 / BRPOPLPUSH 原子地把任务从就绪队列移到 processing 队列, worker
  崩溃后任务不会丢失 (可由 reaper 重新投递).
- ack 时 LREM processing; 失败时 retries++, 超过 max_retries 进死信队列 DLQ.
- handler 通过装饰器或 register() 注册, 按 task_type 分发.
"""
import json
import logging
import time
import uuid
from typing import Callable

from app.services.redis_service import redis_service

logger = logging.getLogger(__name__)

READY_KEY = "mq:ready"
PROCESSING_KEY = "mq:processing"
DLQ_KEY = "mq:dlq"
DEFAULT_MAX_RETRIES = 3


class TaskQueue:
    def __init__(self, ready_key=READY_KEY, processing_key=PROCESSING_KEY, dlq_key=DLQ_KEY):
        self.ready_key = ready_key
        self.processing_key = processing_key
        self.dlq_key = dlq_key
        self._handlers: dict[str, Callable] = {}

    @property
    def client(self):
        return redis_service.client

    def register(self, task_type: str):
        def deco(fn):
            self._handlers[task_type] = fn
            return fn
        return deco

    def enqueue(self, task_type: str, payload: dict, max_retries: int = DEFAULT_MAX_RETRIES) -> str:
        task = {
            "id": uuid.uuid4().hex,
            "type": task_type,
            "payload": payload,
            "retries": 0,
            "max_retries": max_retries,
            "enqueued_at": time.time(),
        }
        self.client.lpush(self.ready_key, json.dumps(task))
        return task["id"]

    def queue_size(self) -> int:
        return self.client.llen(self.ready_key)

    def dlq_size(self) -> int:
        return self.client.llen(self.dlq_key)

    def processing_size(self) -> int:
        return self.client.llen(self.processing_key)

    def consume_one(self, timeout: int = 5):
        """阻塞地取一条任务, 取到的同时移动到 processing 队列."""
        raw = self.client.brpoplpush(self.ready_key, self.processing_key, timeout=timeout)
        if not raw:
            return None
        try:
            task = json.loads(raw)
        except json.JSONDecodeError:
            self.client.lrem(self.processing_key, 1, raw)
            return None
        return raw, task

    def ack(self, raw: str):
        self.client.lrem(self.processing_key, 1, raw)

    def nack(self, raw: str, task: dict, error: str):
        self.client.lrem(self.processing_key, 1, raw)
        task["retries"] += 1
        task["last_error"] = error
        if task["retries"] >= task.get("max_retries", DEFAULT_MAX_RETRIES):
            self.client.lpush(self.dlq_key, json.dumps(task))
            logger.error("task %s moved to DLQ after %d retries: %s", task["id"], task["retries"], error)
        else:
            self.client.lpush(self.ready_key, json.dumps(task))
            logger.warning("task %s requeued (retry %d): %s", task["id"], task["retries"], error)

    def run_worker(self, stop_event=None, timeout: int = 5):
        logger.info("queue worker started, handlers=%s", list(self._handlers))
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            popped = self.consume_one(timeout=timeout)
            if popped is None:
                continue
            raw, task = popped
            handler = self._handlers.get(task["type"])
            if handler is None:
                self.nack(raw, task, error=f"no handler for type={task['type']}")
                continue
            try:
                handler(task["payload"])
                self.ack(raw)
            except Exception as e:
                self.nack(raw, task, error=str(e))

    def purge_all(self):
        self.client.delete(self.ready_key, self.processing_key, self.dlq_key)


task_queue = TaskQueue()


# 注意: 邮件仅用于注册 / 找回密码, 这两类调用必须走同步的 mail_service,
# 以便用户能即时看到 SMTP 失败提示. 因此本队列**不**注册 send_email handler,
# 避免邮件被旁路到异步通道里产生"假成功"的用户体验.
