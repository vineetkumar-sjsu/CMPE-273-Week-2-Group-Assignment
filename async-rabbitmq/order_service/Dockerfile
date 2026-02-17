FROM python:3.11-slim
WORKDIR /app
COPY async-rabbitmq/order_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/ ./common/
COPY async-rabbitmq/order_service/app.py .
EXPOSE 5000
CMD ["python", "app.py"]
