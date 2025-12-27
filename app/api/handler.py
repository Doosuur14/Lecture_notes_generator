import json
import os
import uuid
import datetime
import ydb
import boto3

# -----------------------------
# YDB connection
# -----------------------------
driver = ydb.Driver(
    endpoint=os.environ["YDB_ENDPOINT"],
    database=os.environ["YDB_DATABASE"],
    credentials=ydb.credentials_from_env_variables()
)

driver.wait(fail_fast=True, timeout=5)
session_pool = ydb.SessionPool(driver)

# -----------------------------
# Yandex Message Queue (SQS)
# -----------------------------
sqs = boto3.client(
    "sqs",
    endpoint_url=os.environ["QUEUE_URL"]
)

# -----------------------------
# Main handler
# -----------------------------
def handler(event, context):
    if event["httpMethod"] == "POST":
        return create_task(event)

    return {
        "statusCode": 405,
        "body": "Method Not Allowed"
    }

# -----------------------------
# Create task
# -----------------------------
def create_task(event):
    body = json.loads(event.get("body", "{}"))

    lecture_title = body.get("lecture_title")
    video_url = body.get("video_url")

    if not lecture_title or not video_url:
        return {
            "statusCode": 400,
            "body": "lecture_title and video_url are required"
        }

    task_id = str(uuid.uuid4())
    created_at = datetime.datetime.utcnow()

    def insert_task(session):
        query = """
        DECLARE $task_id AS String;
        DECLARE $created_at AS Timestamp;
        DECLARE $lecture_title AS String;
        DECLARE $video_url AS String;
        DECLARE $status AS String;

        INSERT INTO lecture_tasks
        (task_id, created_at, lecture_title, video_url, status)
        VALUES ($task_id, $created_at, $lecture_title, $video_url, $status);
        """
        session.execute(
            query,
            {
                "$task_id": task_id,
                "$created_at": created_at,
                "$lecture_title": lecture_title,
                "$video_url": video_url,
                "$status": "QUEUED"
            },
            commit_tx=True
        )

    session_pool.retry_operation_sync(insert_task)

    # Send task to queue
    sqs.send_message(
        QueueUrl=os.environ["QUEUE_URL"],
        MessageBody=json.dumps({
            "task_id": task_id
        })
    )

    return {
        "statusCode": 302,
        "headers": {
            "Location": "/tasks"
        }
    }
