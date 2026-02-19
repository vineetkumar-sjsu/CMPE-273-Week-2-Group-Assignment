# CMPE 273 – Group Assignment - Week 2

**Campus Food Ordering System** implemented using three communication patterns:

| Part | Pattern | Tech Stack |
|------|---------|-----------|
| A | Synchronous REST | Flask, requests |
| B | Asynchronous Messaging | Flask, RabbitMQ, pika |
| C | Streaming | Flask, Apache Kafka, kafka-python-ng |

All three parts are fully containerized with Docker Compose.

## Team Members (Group 13)
1. Vineet Kumar
2. Samved Sandeep Joshi
3. Girith Choudhary

## Repo Structure

```
cmpe273-comm-models-lab/
├── common/
│   ├── README.md
│   └── ids.py                  # shared ID generators
├── sync-rest/
│   ├── docker-compose.yml
│   ├── order_service/
│   ├── inventory_service/
│   ├── notification_service/
│   └── tests/
│       ├── test_sync.py
│       └── test_output.txt     # full test run proof
├── async-rabbitmq/
│   ├── docker-compose.yml
│   ├── order_service/
│   ├── inventory_service/
│   ├── notification_service/
│   ├── broker/
│   └── tests/
│       ├── test_async.py
│       └── test_output.txt     # full test run proof
├── streaming-kafka/
│   ├── docker-compose.yml
│   ├── producer_order/
│   ├── inventory_consumer/
│   ├── analytics_consumer/
│   ├── metrics/
│   │   └── metrics_output.json # analytics metrics output
│   └── tests/
│       ├── test_streaming.py
│       ├── test_output.txt     # full test run proof
│       └── replay_evidence.txt # replay before/after proof
└── README.md
```

## Proof / Evidence Files

| Part | File | Description |
|------|------|-------------|
| A | [sync-rest/tests/test_output.txt](../sync-rest/tests/test_output.txt) | Full test run output with all latency measurements |
| B | [async-rabbitmq/tests/test_output.txt](../async-rabbitmq/tests/test_output.txt) | Full test run output showing backlog drain, idempotency, and DLQ |
| C | [streaming-kafka/tests/test_output.txt](../streaming-kafka/tests/test_output.txt) | Full test run output with 10k events, consumer lag, and replay |
| C | [streaming-kafka/tests/replay_evidence.txt](../streaming-kafka/tests/replay_evidence.txt) | Side-by-side replay comparison proving consistent metrics |
| C | [streaming-kafka/metrics/metrics_output.json](../streaming-kafka/metrics/metrics_output.json) | Computed analytics metrics (orders per minute, failure rate) |

## Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for running test scripts locally)
- `pip install requests pika kafka-python-ng` (test dependencies)

---

## Part A: Synchronous REST

### Architecture

```
Client ──POST /order──▶ OrderService ──POST /reserve──▶ InventoryService
                             │
                             └──POST /send──▶ NotificationService
```

Every call is blocking. OrderService waits for Inventory to respond before calling Notification, then returns the final result to the client.

### Build & Run

```bash
cd sync-rest/
docker compose up -d --build
```

Services:
- OrderService: `localhost:6000`
- InventoryService: `localhost:6001`
- NotificationService: `localhost:6002`

### Run Tests

```bash
cd sync-rest/
python tests/test_sync.py
```

Full output: [sync-rest/tests/test_output.txt](../sync-rest/tests/test_output.txt)

### Test Results

**TEST 1 – Baseline Latency (20 requests, no delay)**

```
  req   1  | 201 | confirmed  |    35.2 ms
  req   2  | 201 | confirmed  |    13.0 ms
  req   3  | 201 | confirmed  |     7.9 ms
  req   4  | 201 | confirmed  |     9.0 ms
  req   5  | 201 | confirmed  |     6.8 ms
  req   6  | 201 | confirmed  |     8.5 ms
  req   7  | 201 | confirmed  |     6.9 ms
  req   8  | 201 | confirmed  |     9.6 ms
  req   9  | 201 | confirmed  |     7.2 ms
  req  10  | 201 | confirmed  |     7.5 ms
  req  11  | 201 | confirmed  |     7.8 ms
  req  12  | 201 | confirmed  |     6.9 ms
  req  13  | 201 | confirmed  |     6.5 ms
  req  14  | 201 | confirmed  |     6.6 ms
  req  15  | 201 | confirmed  |     6.4 ms
  req  16  | 201 | confirmed  |     7.2 ms
  req  17  | 201 | confirmed  |     7.2 ms
  req  18  | 201 | confirmed  |     7.0 ms
  req  19  | 201 | confirmed  |     7.0 ms
  req  20  | 201 | confirmed  |    12.7 ms

  --- Summary ---
  min    =     6.4 ms
  max    =    35.2 ms
  mean   =     9.3 ms
  median =     7.2 ms
  stdev  =     6.4 ms
```

**TEST 2 – 2-second Inventory Delay Injection**

```
  req   1  | 201 | confirmed  |  2058.7 ms
  req   2  | 201 | confirmed  |  2032.8 ms
  req   3  | 201 | confirmed  |  2023.7 ms
  req   4  | 201 | confirmed  |  2021.4 ms
  req   5  | 201 | confirmed  |  2019.5 ms
  req   6  | 201 | confirmed  |  2025.7 ms
  req   7  | 201 | confirmed  |  2014.9 ms
  req   8  | 201 | confirmed  |  2021.2 ms
  req   9  | 201 | confirmed  |  2019.5 ms
  req  10  | 201 | confirmed  |  2020.7 ms

  --- Summary (with 2s delay) ---
  min    =  2014.9 ms
  max    =  2058.7 ms
  mean   =  2025.8 ms
  median =  2021.3 ms
```

**TEST 3 – Inventory Forced Failure (FORCE_FAILURE=true)**

```
  req   1  | HTTP 422 | failed     | reason=service_error |    26.2 ms
  req   2  | HTTP 422 | failed     | reason=service_error |     7.9 ms
  req   3  | HTTP 422 | failed     | reason=service_error |     6.4 ms
  req   4  | HTTP 422 | failed     | reason=service_error |     7.2 ms
  req   5  | HTTP 422 | failed     | reason=service_error |     7.5 ms
```

**TEST 4 – Inventory Completely Down (service stopped)**

```
  req   1  | HTTP 503 | failed     | reason=inventory_unavailable |    44.8 ms
  req   2  | HTTP 503 | failed     | reason=inventory_unavailable |     8.8 ms
  req   3  | HTTP 503 | failed     | reason=inventory_unavailable |     8.3 ms
```

### Latency Comparison Table

| Scenario | Mean (ms) | Median (ms) |
|----------|-----------|-------------|
| Baseline (no delay) | 9.3 | 7.2 |
| 2s inventory delay | 2025.8 | 2021.3 |

**Delta: ~2016.5 ms**

### Analysis

The ~2000 ms increase directly matches the injected sleep because the synchronous call chain is fully blocking. OrderService cannot start processing the next step (notification) or return a response until the Inventory call completes. This is the fundamental tradeoff of synchronous communication: simplicity and strong consistency at the cost of tight coupling. A slow downstream service directly degrades the upstream service's response time by the exact amount of the delay.

When Inventory is forced to fail (FORCE_FAILURE=true), the service itself is still running so it returns HTTP 500 quickly. OrderService maps that to a 422 with `reason=service_error`. The latency stays low (~7 ms) because there's no network delay — the error is immediate.

When Inventory is completely down (container stopped), OrderService catches the `ConnectionError` and returns HTTP 503 within ~9-45 ms. The 5-second timeout is not reached because the TCP connection is refused immediately rather than hanging.

---

## Part B: Asynchronous Messaging (RabbitMQ)

### Architecture

```
Client ──POST /order──▶ OrderService ──publish──▶ [RabbitMQ: orders exchange]
                                                        │
                                          ┌─────────────┼──────────────┐
                                          ▼                            ▼
                                  InventoryService             (fanout to other
                                     │                          consumers)
                                     │ publish
                                     ▼
                              [inventory_events exchange]
                                     │
                               ┌─────┴─────┐
                               ▼           ▼
                        OrderService   NotificationService
                       (status update)  (send confirmation)
```

OrderService writes the order locally, publishes an `OrderPlaced` event to RabbitMQ, and returns `202 Accepted` immediately. InventoryService picks up the message, reserves stock, and publishes `InventoryReserved` or `InventoryFailed`. NotificationService consumes inventory results and logs the notification.

### Build & Run

```bash
cd async-rabbitmq/
docker compose up -d --build
```

Services:
- OrderService: `localhost:6000`
- RabbitMQ Management UI: `localhost:15672` (guest/guest)

### Run Tests

```bash
cd async-rabbitmq/
python tests/test_async.py
```

Full output: [async-rabbitmq/tests/test_output.txt](../async-rabbitmq/tests/test_output.txt)

### Test Results

**TEST 1 – Backlog Drain (Kill Inventory for 60s, Publish Orders, Restart)**

```
  Stopping inventory-service...
  Publishing 15 orders while inventory is down...
    order 1: 202 -> ORD-1771300361345-874302bf
    order 2: 202 -> ORD-1771300361479-d4cbd62c
    order 3: 202 -> ORD-1771300361603-36acfc77
    order 4: 202 -> ORD-1771300361725-a128ea71
    order 5: 202 -> ORD-1771300361838-763e6b05
    order 6: 202 -> ORD-1771300361957-d8649ac4
    order 7: 202 -> ORD-1771300362077-11e4d447
    order 8: 202 -> ORD-1771300362197-c1a8a337
    order 9: 202 -> ORD-1771300362315-ddeab4ab
    order 10: 202 -> ORD-1771300362436-9bb9ec99
    order 11: 202 -> ORD-1771300362557-26afe7cd
    order 12: 202 -> ORD-1771300362675-ff13e28f
    order 13: 202 -> ORD-1771300362794-0fcf770d
    order 14: 202 -> ORD-1771300362911-e7ed5739
    order 15: 202 -> ORD-1771300363027-3d6f427e

  Queue depth (inventory_orders): 15
  Messages are queued in RabbitMQ waiting for a consumer.

  Restarting inventory-service...
  Watching backlog drain...
    t=  0s  queue depth = 0
  Backlog fully drained!

  Orders confirmed: 15/15
```

All 15 orders were accepted (HTTP 202) while Inventory was completely down. The messages sat safely in the RabbitMQ queue (`inventory_orders` depth = 15). When Inventory restarted, it consumed the entire backlog almost instantly (queue depth dropped to 0 within the first poll interval) and all 15 orders were confirmed.

**TEST 2 – Idempotency (Duplicate Message Delivery)**

```
  Published event (attempt 1) with event_id=idempotency-test-12345
  Published event (attempt 2) with event_id=idempotency-test-12345

  Inventory service logs (last 30 lines):
    inventory-service-1  | INFO:inventory_service:[ORD-1771300361345-874302bf] reserved 1x pizza (remaining=99)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300361479-d4cbd62c] reserved 1x pizza (remaining=98)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300361603-36acfc77] reserved 1x pizza (remaining=97)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300361725-a128ea71] reserved 1x pizza (remaining=96)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300361838-763e6b05] reserved 1x pizza (remaining=95)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300361957-d8649ac4] reserved 1x pizza (remaining=94)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300362077-11e4d447] reserved 1x pizza (remaining=93)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300362197-c1a8a337] reserved 1x pizza (remaining=92)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300362315-ddeab4ab] reserved 1x pizza (remaining=91)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300362436-9bb9ec99] reserved 1x pizza (remaining=90)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300362557-26afe7cd] reserved 1x pizza (remaining=89)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300362675-ff13e28f] reserved 1x pizza (remaining=88)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300362794-0fcf770d] reserved 1x pizza (remaining=87)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300362911-e7ed5739] reserved 1x pizza (remaining=86)
    inventory-service-1  | INFO:inventory_service:[ORD-1771300363027-3d6f427e] reserved 1x pizza (remaining=85)
    inventory-service-1  | INFO:inventory_service:[ORD-IDEMP-001] reserved 5x soda (remaining=195)
    inventory-service-1  | WARNING:inventory_service:[ORD-IDEMP-001] duplicate event_id=idempotency-test-12345, skipping (idempotent)

  If inventory only reserved 5 (not 10), idempotency is working.
  The second message with the same event_id was skipped.
```

**Idempotency Strategy:** Each event carries a unique `event_id` generated at publish time. The Inventory consumer maintains an in-memory set of processed event IDs (`processed_events`). Before reserving stock, it checks if the `event_id` has already been handled. If yes, it ACKs the message without modifying inventory. The log line `duplicate event_id=idempotency-test-12345, skipping (idempotent)` confirms the second delivery was ignored. Only 5 units of soda were reserved (not 10), proving the guard works.

In a production system, this set would be backed by a database or Redis to survive restarts. For this lab, in-memory tracking is sufficient to demonstrate the pattern.

**TEST 3 – DLQ / Poison Message Handling**

```
  Published malformed (non-JSON) message.
  Published JSON with missing required fields.

  DLQ depth (orders_dlq): 2
  Both poison messages should be in the dead-letter queue.

  Inventory logs (malformed handling):
    inventory-service-1  | ERROR:inventory_service:malformed message, sending to DLQ: b'THIS IS NOT JSON {{{corrupted'
    inventory-service-1  | ERROR:inventory_service:[unknown] missing required fields, nack to DLQ
```

The `inventory_orders` queue is configured with `x-dead-letter-exchange: orders_dlx`. When the consumer calls `basic_nack(requeue=False)` on a bad message, RabbitMQ routes it to the dead-letter exchange which is bound to `orders_dlq`. Two poison messages were published (one non-JSON garbage, one JSON missing required fields), and both landed in the DLQ (depth = 2). This prevents poison messages from blocking the main queue while preserving them for inspection.

---

## Part C: Streaming (Kafka)

### Architecture

```
Client ──POST /order──▶ ProducerOrder ──produce──▶ [OrderEvents topic]
                                                        │
                                          ┌─────────────┼──────────────┐
                                          ▼                            ▼
                                 InventoryConsumer             AnalyticsConsumer
                                     │                         (reads OrderEvents
                                     │ produce                  + InventoryEvents,
                                     ▼                          computes metrics)
                              [InventoryEvents topic]
                                     │
                                     ▼
                              AnalyticsConsumer
```

The ProducerOrder service publishes `OrderPlaced` events to the `OrderEvents` topic. InventoryConsumer reads from `OrderEvents`, processes reservations, and writes results to `InventoryEvents`. AnalyticsConsumer subscribes to both topics and computes rolling metrics (orders per minute, failure rate).

### Build & Run

```bash
cd streaming-kafka/
docker compose up -d --build
```

Services:
- ProducerOrder: `localhost:6000`
- Kafka broker: `localhost:29092` (external), `kafka:9092` (internal)

### Run Tests

```bash
cd streaming-kafka/
python tests/test_streaming.py
```

Full output: [streaming-kafka/tests/test_output.txt](../streaming-kafka/tests/test_output.txt)

Replay evidence: [streaming-kafka/tests/replay_evidence.txt](../streaming-kafka/tests/replay_evidence.txt)

### Test Results

**TEST 1 – Produce 10,000 Events**

```
  Published: 10000 events in 0.9s
  Fail rate injected: 10%
```

10,000 `OrderPlaced` events published through Kafka in under 1 second using the `/bulk` endpoint. A 10% failure rate was injected (random orders flagged with `force_fail=True`) to generate a mix of `InventoryReserved` and `InventoryFailed` downstream events for analytics.

**TEST 2 – Consumer Lag**

```
  inventory-group lag:
    GROUP           TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                             HOST            CLIENT-ID
    inventory-group OrderEvents     0          10000           10000           0               kafka-python-2.2.2-8ebcf2f7-b77d-4003-bf5d-904f2391570b /172.20.0.4     kafka-python-2.2.2

  analytics-group lag:
    GROUP           TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG             CONSUMER-ID                                             HOST            CLIENT-ID
    analytics-group InventoryEvents 0          10000           10000           0               kafka-python-2.2.2-f6d60c71-a900-4c49-a81c-a524520f307e /172.20.0.6     kafka-python-2.2.2
    analytics-group OrderEvents     0          10000           10000           0               kafka-python-2.2.2-f6d60c71-a900-4c49-a81c-a524520f307e /172.20.0.6     kafka-python-2.2.2
```

Both consumer groups have caught up (LAG = 0). The `CURRENT-OFFSET` matches `LOG-END-OFFSET` at 10000 for every topic-partition. Under throttling or heavy load, the LAG column would show the number of unprocessed messages. Kafka preserves the messages on disk regardless, so consumers can fall behind without data loss.

**TEST 3 – Replay (Reset Consumer Offset and Recompute)**

First replay run (consumer group: `analytics-group-replay-1771300498`):

```
  total_orders_seen: 10000
  total_reserved: 8976
  total_failed: 1024
  duration_minutes: 1
  avg_orders_per_minute: 10000.0
  failure_rate_percent: 10.24
```

Second replay run (consumer group: `analytics-group-replay-1771300537`):

```
  total_orders_seen: 10000
  total_reserved: 8976
  total_failed: 1024
  duration_minutes: 1
  avg_orders_per_minute: 10000.0
  failure_rate_percent: 10.24
```

Comparison:

| Metric | Replay Run 1 | Replay Run 2 |
|--------|-------------|-------------|
| total_orders_seen | 10000 | 10000 |
| total_reserved | 8976 | 8976 |
| total_failed | 1024 | 1024 |
| avg_orders_per_minute | 10000.0 | 10000.0 |
| failure_rate_percent | 10.24 | 10.24 |

**Replay produced CONSISTENT metrics.** Each replay uses a fresh consumer group (`analytics-group-replay-<timestamp>`) with `auto_offset_reset=earliest`, which forces it to read all events from offset 0. Since Kafka retains events on disk (unlike RabbitMQ which deletes consumed messages), we can recompute the exact same metrics from the same event stream. The numbers match because the input data is immutable and the analytics computation is deterministic — the same events always produce the same counts and rates.

Full replay evidence with logs: [streaming-kafka/tests/replay_evidence.txt](../streaming-kafka/tests/replay_evidence.txt)

### Metrics Output

The metrics report is written to [`streaming-kafka/metrics/metrics_output.json`](../streaming-kafka/metrics/metrics_output.json):

```json
{
  "total_orders_seen": 10000,
  "total_reserved": 8976,
  "total_failed": 1024,
  "duration_minutes": 1,
  "avg_orders_per_minute": 10000.0,
  "failure_rate_percent": 10.24,
  "orders_per_minute_buckets": { "1771300380": 10000 },
  "failures_per_minute_buckets": { "1771300380": 1024 }
}
```

# Common Utilities

Shared helper functions used across all three communication models.

## ids.py

Provides two helpers:

- `generate_order_id()` – returns a string like `ORD-1707000000000-a1b2c3d4` combining a millisecond timestamp with a short random suffix. This makes IDs roughly sortable by creation time while staying globally unique.
- `generate_event_id()` – returns a plain hex UUID, used as a message/event identifier for idempotency checks and tracing.

## Usage

Each service copies or mounts this module so that order and event IDs stay consistent across the sync, async, and streaming implementations.

---

## Summary: Communication Model Comparison

| Property | Sync REST | Async (RabbitMQ) | Streaming (Kafka) |
|----------|-----------|------------------|--------------------|
| Coupling | Tight — caller blocks until response | Loose — fire and forget | Loose — producers and consumers independent |
| Latency impact | Downstream delay directly adds to response time | No impact on producer; messages queue up | No impact on producer; consumers can lag |
| Failure handling | Immediate error propagation (503, timeout) | Messages survive consumer downtime | Messages survive consumer downtime; replay possible |
| Ordering | Sequential, deterministic | FIFO within a single queue | Partition-level ordering |
| Replay | Not possible | Not possible (messages are consumed) | Possible — reset offsets and recompute |
| Complexity | Simplest | Moderate (broker, exchanges, DLQ) | Highest (broker, topics, consumer groups, offsets) |
| Best for | Simple request/response, strong consistency needs | Task queuing, decoupled workflows | Event sourcing, analytics, audit logs |
