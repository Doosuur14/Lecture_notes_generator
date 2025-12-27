import json
import os
import uuid
import datetime
import ydb
import boto3
from html import escape

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
# Yandex Message Queue
# -----------------------------
sqs = boto3.client(
    "sqs",
    endpoint_url=os.environ["QUEUE_URL"]
)

# -----------------------------
# Main handler
# -----------------------------
def handler(event, context):
    method = event["httpMethod"]
    path = event.get("path", "/")

    if method == "POST":
        return create_task(event)

    if method == "GET" and path == "/tasks":
        return list_tasks()

    if method == "GET":
        return render_form()

    return {
        "statusCode": 405,
        "body": "Method Not Allowed"
    }

# -----------------------------
# HTML: Create task form
# -----------------------------
def render_form():
    html = """
    <html>
    <head><title>Lecture Notes Generator</title></head>
    <body>
        <h1>Create lecture notes</h1>
        <form method="POST">
            <label>Lecture title:</label><br>
            <input type="text" name="lecture_title" required><br><br>

            <label>Yandex Disk video link:</label><br>
            <input type="text" name="video_url" required><br><br>

            <button type="submit">Create notes</button>
        </form>
        <br>
        <a href="/tasks">View tasks</a>
    </body>
    </html>
    """
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": html
    }

# -----------------------------
# Create task
# -----------------------------
def create_task(event):
    body = event.get("body", "")
    params = parse_form(body)

    lecture_title = params.get("lecture_title")
    video_url = params.get("video_url")

    if not lecture_title or not video_url:
        return {"statusCode": 400, "body": "Missing fields"}

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

    sqs.send_message(
        QueueUrl=os.environ["QUEUE_URL"],
        MessageBody=json.dumps({"task_id": task_id})
    )

    return {
        "statusCode": 302,
        "headers": {"Location": "/tasks"}
    }

# -----------------------------
# List tasks
# -----------------------------
def list_tasks():
    def select_tasks(session):
        result = session.execute(
            """
            SELECT task_id, created_at, lecture_title, video_url, status, pdf_url, error_message
            FROM lecture_tasks
            ORDER BY created_at DESC;
            """,
            commit_tx=True
        )
        return result[0].rows

    rows = session_pool.retry_operation_sync(select_tasks)

    html = """
    <html>
    <head><title>Tasks</title></head>
    <body>
        <h1>All tasks</h1>
        <a href="/">Create new task</a>
        <br><br>
        <table border="1" cellpadding="5">
            <tr>
                <th>Date</th>
                <th>ID</th>
                <th>Title</th>
                <th>Video</th>
                <th>Status</th>
                <th>PDF</th>
                <th>Error</th>
            </tr>
    """

    for r in rows:
        pdf_link = (
            f'<a href="{escape(r.pdf_url)}">Download</a>'
            if r.pdf_url and r.status == "DONE"
            else ""
        )

        error = escape(r.error_message) if r.error_message else ""

        html += f"""
        <tr>
            <td>{r.created_at}</td>
            <td>{escape(r.task_id)}</td>
            <td>{escape(r.lecture_title)}</td>
            <td><a href="{escape(r.video_url)}">link</a></td>
            <td>{escape(r.status)}</td>
            <td>{pdf_link}</td>
            <td>{error}</td>
        </tr>
        """

    html += """
        </table>
        <br>
        <p>Refresh page to update status.</p>
    </body>
    </html>
    """

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html"},
        "body": html
    }

# -----------------------------
# Helpers
# -----------------------------
def parse_form(body):
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            k, v = pair.split("=", 1)
            params[k] = v.replace("+", " ")
    return params

