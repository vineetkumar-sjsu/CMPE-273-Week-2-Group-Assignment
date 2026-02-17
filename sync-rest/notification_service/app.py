import logging

from flask import Flask, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification_service")

sent_log = []


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "notification_service"})


@app.route("/send", methods=["POST"])
def send_notification():
    data = request.get_json(force=True)
    order_id = data.get("order_id", "n/a")
    message = data.get("message", "")

    logger.info(f"[{order_id}] notification: {message}")
    sent_log.append({"order_id": order_id, "message": message})

    return jsonify({"sent": True, "order_id": order_id}), 200


@app.route("/log", methods=["GET"])
def get_log():
    return jsonify(sent_log)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
