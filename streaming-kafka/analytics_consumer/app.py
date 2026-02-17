import os
import json
import time
import logging
from collections import defaultdict

from kafka import KafkaConsumer, TopicPartition
from kafka.errors import NoBrokersAvailable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("analytics_consumer")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
ORDER_TOPIC = "OrderEvents"
INVENTORY_TOPIC = "InventoryEvents"
GROUP_ID = os.getenv("CONSUMER_GROUP", "analytics-group")
METRICS_FILE = os.getenv("METRICS_FILE", "/app/metrics_output.json")


def wait_for_kafka():
    from kafka import KafkaProducer
    for attempt in range(30):
        try:
            p = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
            p.close()
            return
        except NoBrokersAvailable:
            logger.warning(f"kafka not available, retrying ({attempt+1}/30)...")
            time.sleep(3)
    raise RuntimeError("kafka never became available")


class MetricsComputer:
    def __init__(self):
        self.total_orders = 0
        self.total_reserved = 0
        self.total_failed = 0
        self.orders_per_minute = defaultdict(int)
        self.failures_per_minute = defaultdict(int)
        self.first_ts = None
        self.last_ts = None

    def record_order(self, event):
        self.total_orders += 1
        ts = event.get("timestamp", time.time())
        minute_bucket = int(ts / 60) * 60
        self.orders_per_minute[minute_bucket] += 1
        if self.first_ts is None or ts < self.first_ts:
            self.first_ts = ts
        if self.last_ts is None or ts > self.last_ts:
            self.last_ts = ts

    def record_inventory_result(self, event):
        etype = event.get("event_type", "")
        ts = event.get("timestamp", time.time())
        minute_bucket = int(ts / 60) * 60
        if etype == "InventoryReserved":
            self.total_reserved += 1
        elif etype == "InventoryFailed":
            self.total_failed += 1
            self.failures_per_minute[minute_bucket] += 1

    def compute_report(self):
        duration_min = 1
        if self.first_ts and self.last_ts and self.last_ts > self.first_ts:
            duration_min = max((self.last_ts - self.first_ts) / 60.0, 1)

        avg_opm = self.total_orders / duration_min if duration_min > 0 else 0
        failure_rate = (self.total_failed / (self.total_reserved + self.total_failed) * 100
                        if (self.total_reserved + self.total_failed) > 0 else 0)

        report = {
            "total_orders_seen": self.total_orders,
            "total_reserved": self.total_reserved,
            "total_failed": self.total_failed,
            "duration_minutes": round(duration_min, 2),
            "avg_orders_per_minute": round(avg_opm, 2),
            "failure_rate_percent": round(failure_rate, 2),
            "orders_per_minute_buckets": dict(self.orders_per_minute),
            "failures_per_minute_buckets": dict(self.failures_per_minute),
        }
        return report

    def save_report(self, path=None):
        path = path or METRICS_FILE
        report = self.compute_report()
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"metrics report saved to {path}")
        return report


def run_analytics(replay=False):
    wait_for_kafka()

    metrics = MetricsComputer()

    consumer = KafkaConsumer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=GROUP_ID if not replay else f"{GROUP_ID}-replay-{int(time.time())}",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    )
    consumer.subscribe([ORDER_TOPIC, INVENTORY_TOPIC])

    logger.info(f"analytics_consumer started (replay={replay}, group={consumer.config['group_id']})")

    idle_count = 0
    max_idle = 15  # stop after 15 consecutive empty polls (when doing replay)

    while True:
        records = consumer.poll(timeout_ms=2000)
        if not records:
            idle_count += 1
            if replay and idle_count >= max_idle:
                logger.info("replay: no more records, finishing")
                break
            if not replay and idle_count >= 300:
                # in normal mode, periodically save
                pass
            continue

        idle_count = 0
        for tp, messages in records.items():
            for msg in messages:
                event = msg.value
                topic = msg.topic

                if topic == ORDER_TOPIC:
                    metrics.record_order(event)
                elif topic == INVENTORY_TOPIC:
                    metrics.record_inventory_result(event)

        # periodically log and save
        if metrics.total_orders % 1000 == 0 and metrics.total_orders > 0:
            report = metrics.compute_report()
            logger.info(
                f"[live] orders={report['total_orders_seen']} "
                f"reserved={report['total_reserved']} "
                f"failed={report['total_failed']} "
                f"opm={report['avg_orders_per_minute']} "
                f"fail%={report['failure_rate_percent']}"
            )

    report = metrics.save_report()
    logger.info("=== FINAL METRICS REPORT ===")
    for k, v in report.items():
        if not isinstance(v, dict):
            logger.info(f"  {k}: {v}")

    consumer.close()
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", action="store_true", help="reset offset and replay all events")
    args = parser.parse_args()

    run_analytics(replay=args.replay)
