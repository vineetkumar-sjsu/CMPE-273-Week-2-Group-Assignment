FROM python:3.11-slim
WORKDIR /app
COPY sync-rest/notification_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY sync-rest/notification_service/app.py .
EXPOSE 5002
CMD ["python", "app.py"]
