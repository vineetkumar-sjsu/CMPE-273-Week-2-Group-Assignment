import os
import json
import time
import logging

from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inventory_consumer")

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
ORDER_TOPIC = "OrderEvents"
INVENTORY_TOPIC = "InventoryEvents"
GROUP_ID = "inventory-group"

stock = {
    "burger": 5000,
    "pizza": 5000,
    "soda": 10000,
    "fries": 7000,
    "salad": 4000,
}


def wait_for_kafka():
    for attempt in range(30):
        try:
            p = KafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP)
            p.close()
            return
        except NoBrokersAvailable:
            logger.warning(f"kafka not available, retrying ({attempt+1}/30)...")
            time.sleep(3)
    raise RuntimeError("kafka never became available")


def main():
    wait_for_kafka()

    consumer = KafkaConsumer(
        ORDER_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        consumer_timeout_ms=1000,  # poll timeout
    )

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )

    logger.info(f"inventory_consumer started, group={GROUP_ID}")
    logger.info(f"initial stock: {stock}")

    processed = 0
    while True:
        records = consumer.poll(timeout_ms=1000)
        for tp, messages in records.items():
            for msg in messages:
                event = msg.value
                order_id = event.get("order_id", "unknown")
                item = event.get("item", "")
                qty = event.get("qty", 1)
                force_fail = event.get("force_fail", False)

                if force_fail or item not in stock or stock.get(item, 0) < qty:
                    reason = "forced_failure" if force_fail else (
                        "item_not_found" if item not in stock else "insufficient_stock"
                    )
                    result = {
                        "event_type": "InventoryFailed",
                        "order_id": order_id,
                        "item": item,
                        "reason": reason,
                        "timestamp": time.time(),
                    }
                else:
                    stock[item] -= qty
                    result = {
                        "event_type": "InventoryReserved",
                        "order_id": order_id,
                        "item": item,
                        "qty": qty,
                        "remaining": stock[item],
                        "timestamp": time.time(),
                    }

                producer.send(INVENTORY_TOPIC, value=result)
                processed += 1

                if processed % 500 == 0:
                    logger.info(f"processed {processed} events so far")

        # small sleep to avoid busy loop when idle
        if not records:
            time.sleep(0.5)


if __name__ == "__main__":
    main()
