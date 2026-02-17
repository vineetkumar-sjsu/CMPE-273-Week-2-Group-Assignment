FROM python:3.11-slim
WORKDIR /app
COPY streaming-kafka/analytics_consumer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/ ./common/
COPY streaming-kafka/analytics_consumer/app.py .
CMD ["python", "app.py"]
