FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV YDB_ENDPOINT=""
ENV YDB_DATABASE=""
ENV QUEUE_URL=""
ENV YC_TOKEN=""

CMD ["python", "handler.py"]
