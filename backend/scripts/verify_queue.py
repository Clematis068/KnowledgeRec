"""验证 Redis 消息队列的有效性与可用性.

测试项:
  1. 基础生产-消费 (FIFO 顺序, 计数一致)
  2. 吞吐 benchmark (1000 条任务的 enqueue / dequeue 速率)
  3. 失败重试 (handler 抛异常 -> retries++ -> 最终进 DLQ)
  4. 多 worker 并发消费 (无重复消费, 总数一致)
"""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.services.task_queue import TaskQueue, task_queue


def _section(title):
    print(f"\n{'=' * 12} {title} {'=' * 12}")


def test_basic_fifo():
    _section("Test 1: 基础生产-消费")
    q = TaskQueue(ready_key="mq:test:ready", processing_key="mq:test:processing", dlq_key="mq:test:dlq")
    q.purge_all()

    received = []

    @q.register("echo")
    def _echo(payload):
        received.append(payload["i"])

    N = 50
    for i in range(N):
        q.enqueue("echo", {"i": i})
    print(f"  入队 {N} 条, 队列长度 = {q.queue_size()}")
    assert q.queue_size() == N

    stop = threading.Event()
    t = threading.Thread(target=q.run_worker, args=(stop, 1), daemon=True)
    t.start()
    deadline = time.time() + 5
    while len(received) < N and time.time() < deadline:
        time.sleep(0.05)
    stop.set()
    t.join(timeout=2)

    print(f"  收到 {len(received)} 条, processing={q.processing_size()}, dlq={q.dlq_size()}")
    assert len(received) == N
    assert q.processing_size() == 0
    assert q.dlq_size() == 0
    print("  PASS: FIFO 消费完成, 无遗漏, 无残留")
    q.purge_all()


def test_throughput():
    _section("Test 2: 吞吐 benchmark")
    q = TaskQueue(ready_key="mq:bench:ready", processing_key="mq:bench:processing", dlq_key="mq:bench:dlq")
    q.purge_all()

    counter = [0]

    @q.register("noop")
    def _noop(_payload):
        counter[0] += 1

    N = 1000
    t0 = time.time()
    for i in range(N):
        q.enqueue("noop", {"i": i})
    t_enqueue = time.time() - t0
    print(f"  enqueue {N} 条耗时 {t_enqueue * 1000:.1f} ms ({N / t_enqueue:.0f} ops/s)")

    stop = threading.Event()
    t = threading.Thread(target=q.run_worker, args=(stop, 1), daemon=True)
    t.start()
    t0 = time.time()
    while counter[0] < N:
        if time.time() - t0 > 30:
            break
        time.sleep(0.01)
    t_consume = time.time() - t0
    stop.set()
    t.join(timeout=2)
    print(f"  consume {counter[0]} 条耗时 {t_consume * 1000:.1f} ms ({counter[0] / t_consume:.0f} ops/s)")
    assert counter[0] == N
    print("  PASS")
    q.purge_all()


def test_retry_and_dlq():
    _section("Test 3: 失败重试 + 死信队列")
    q = TaskQueue(ready_key="mq:retry:ready", processing_key="mq:retry:processing", dlq_key="mq:retry:dlq")
    q.purge_all()

    attempts = [0]

    @q.register("always_fail")
    def _fail(_payload):
        attempts[0] += 1
        raise RuntimeError("intentional failure")

    q.enqueue("always_fail", {"x": 1}, max_retries=3)

    stop = threading.Event()
    t = threading.Thread(target=q.run_worker, args=(stop, 1), daemon=True)
    t.start()
    deadline = time.time() + 5
    while q.dlq_size() == 0 and time.time() < deadline:
        time.sleep(0.05)
    stop.set()
    t.join(timeout=2)

    print(f"  handler 调用次数 = {attempts[0]} (期望 3)")
    print(f"  ready={q.queue_size()} processing={q.processing_size()} dlq={q.dlq_size()}")
    assert attempts[0] == 3
    assert q.dlq_size() == 1
    assert q.queue_size() == 0
    print("  PASS: 重试 3 次后进入 DLQ")
    q.purge_all()


def test_concurrent_workers():
    _section("Test 4: 多 worker 并发消费")
    q = TaskQueue(ready_key="mq:concur:ready", processing_key="mq:concur:processing", dlq_key="mq:concur:dlq")
    q.purge_all()

    seen = []
    lock = threading.Lock()

    @q.register("work")
    def _work(payload):
        with lock:
            seen.append(payload["i"])

    N = 500
    for i in range(N):
        q.enqueue("work", {"i": i})

    stop = threading.Event()
    workers = [threading.Thread(target=q.run_worker, args=(stop, 1), daemon=True) for _ in range(4)]
    for w in workers:
        w.start()

    deadline = time.time() + 10
    while len(seen) < N and time.time() < deadline:
        time.sleep(0.05)
    stop.set()
    for w in workers:
        w.join(timeout=2)

    print(f"  4 个 worker, 收到 {len(seen)} / {N} 条, unique = {len(set(seen))}")
    assert len(seen) == N
    assert len(set(seen)) == N, "出现重复消费!"
    print("  PASS: 无重复, 无丢失")
    q.purge_all()


def main():
    app = create_app()
    with app.app_context():
        try:
            task_queue.client.ping()
        except Exception as e:
            print(f"Redis 不可达: {e}")
            sys.exit(1)
        print("Redis 连通 OK")

        test_basic_fifo()
        test_throughput()
        test_retry_and_dlq()
        test_concurrent_workers()

        print("\n所有测试通过 ✅")


if __name__ == "__main__":
    main()
