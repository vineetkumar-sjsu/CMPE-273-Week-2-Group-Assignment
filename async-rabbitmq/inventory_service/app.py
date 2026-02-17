import os
import json
import time
import logging

import pika

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inventory_service")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))

# in-memory stock and idempotency tracking
stock = {
    "burger": 100,
    "pizza": 100,
    "soda": 200,
    "fries": 150,
    "salad": 80,
}

processed_events = set()  # tracks event_ids we already handled


def get_rabbit_connection():
    for attempt in range(20):
        try:
            params = pika.ConnectionParameters(
                host=RABBITMQ_HOST, port=RABBITMQ_PORT,
                heartbeat=600,
                connection_attempts=3, retry_delay=2,
            )
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError:
            logger.warning(f"rabbitmq not ready, retrying ({attempt+1}/20)...")
            time.sleep(3)
    raise RuntimeError("could not connect to rabbitmq")


def publish_inventory_event(ch, event):
    ch.exchange_declare(exchange="inventory_events", exchange_type="fanout", durable=True)
    ch.basic_publish(
        exchange="inventory_events",
        routing_key="",
        body=json.dumps(event),
        properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
    )


def process_order(ch, method, properties, body):
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        logger.error(f"malformed message, sending to DLQ: {body[:200]}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    event_id = event.get("event_id", "")
    order_id = event.get("order_id", "unknown")
    item = event.get("item", "")
    qty = event.get("qty", 0)

    if not event_id or not order_id or not item:
        logger.error(f"[{order_id}] missing required fields, nack to DLQ")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        return

    # idempotency check
    if event_id in processed_events:
        logger.warning(f"[{order_id}] duplicate event_id={event_id}, skipping (idempotent)")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # try to reserve
    if item not in stock:
        logger.warning(f"[{order_id}] item '{item}' not in stock catalog")
        result_event = {
            "event_type": "InventoryFailed",
            "order_id": order_id,
            "reason": "item_not_found",
            "timestamp": time.time(),
        }
        publish_inventory_event(ch, result_event)
        processed_events.add(event_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    if stock[item] < qty:
        logger.warning(f"[{order_id}] insufficient stock for '{item}'")
        result_event = {
            "event_type": "InventoryFailed",
            "order_id": order_id,
            "reason": "insufficient_stock",
            "timestamp": time.time(),
        }
        publish_inventory_event(ch, result_event)
        processed_events.add(event_id)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    stock[item] -= qty
    logger.info(f"[{order_id}] reserved {qty}x {item} (remaining={stock[item]})")

    result_event = {
        "event_type": "InventoryReserved",
        "order_id": order_id,
        "item": item,
        "qty": qty,
        "remaining": stock[item],
        "timestamp": time.time(),
    }
    publish_inventory_event(ch, result_event)
    processed_events.add(event_id)
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    conn = get_rabbit_connection()
    ch = conn.channel()

    # declare exchange and queues
    ch.exchange_declare(exchange="orders", exchange_type="fanout", durable=True)

    # main queue with dead-letter exchange
    ch.exchange_declare(exchange="orders_dlx", exchange_type="fanout", durable=True)
    ch.queue_declare(queue="orders_dlq", durable=True)
    ch.queue_bind(exchange="orders_dlx", queue="orders_dlq")

    ch.queue_declare(
        queue="inventory_orders",
        durable=True,
        arguments={
            "x-dead-letter-exchange": "orders_dlx",
        },
    )
    ch.queue_bind(exchange="orders", queue="inventory_orders")

    ch.basic_qos(prefetch_count=1)
    ch.basic_consume(queue="inventory_orders", on_message_callback=process_order)

    logger.info("inventory_service listening on 'inventory_orders' queue...")
    logger.info(f"initial stock: {stock}")
    ch.start_consuming()


if __name__ == "__main__":
    main()
