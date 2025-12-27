import json
import os
import tempfile
import requests
import ydb
import boto3
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# -----------------------------
# Environment variables
# -----------------------------
YDB_ENDPOINT = os.environ["YDB_ENDPOINT"]
YDB_DATABASE = os.environ["YDB_DATABASE"]
BUCKET_NAME = os.environ["BUCKET_NAME"]
DISK_API_TOKEN = os.environ["DISK_API_TOKEN"]

# -----------------------------
# YDB connection
# -----------------------------
driver = ydb.Driver(
    endpoint=YDB_ENDPOINT,
    database=YDB_DATABASE,
    credentials=ydb.credentials_from_env_variables()
)
driver.wait(fail_fast=True, timeout=5)
session_pool = ydb.SessionPool(driver)

# -----------------------------
# Object Storage (S3)
# -----------------------------
s3 = boto3.client("s3")

# -----------------------------
# Worker entry point
# -----------------------------
def handler(event, context):
    for record in event["messages"]:
        body = json.loads(record["details"]["message"]["body"])
        task_id = body["task_id"]

        try:
            update_status(task_id, "PROCESSING")
            process_task(task_id)
            update_status(task_id, "DONE")
        except Exception as e:
            update_error(task_id, str(e))

# -----------------------------
# Main processing
# -----------------------------
def process_task(task_id):
    task = get_task(task_id)

    # 1. Validate Yandex Disk link
    file_info = validate_disk_link(task["video_url"])

    # 2. Download video
    video_path = download_file(file_info["file"])

    # 3. Fake speech-to-text (for demo / tests)
    transcript = f"Transcript for lecture: {task['lecture_title']}"

    # 4. Fake GPT summary (replace with YandexGPT later)
    summary = f"Lecture notes:\n\n{transcript}"

    # 5. Generate PDF
    pdf_path = generate_pdf(task["lecture_title"], summary)

    # 6. Upload PDF
    pdf_url = upload_pdf(task_id, pdf_path)

    # 7. Save PDF URL
    save_pdf_url(task_id, pdf_url)

# -----------------------------
# YDB helpers
# -----------------------------
def get_task(task_id):
    def select(session):
        res = session.execute(
            """
            DECLARE $task_id AS String;
            SELECT lecture_title, video_url
            FROM lecture_tasks
            WHERE task_id = $task_id;
            """,
            {"$task_id": task_id},
            commit_tx=True
        )
        return res[0].rows[0]

    row = session_pool.retry_operation_sync(select)
    return {
        "lecture_title": row.lecture_title,
        "video_url": row.video_url
    }

def update_status(task_id, status):
    def update(session):
        session.execute(
            """
            DECLARE $task_id AS String;
            DECLARE $status AS String;

            UPDATE lecture_tasks
            SET status = $status
            WHERE task_id = $task_id;
            """,
            {"$task_id": task_id, "$status": status},
            commit_tx=True
        )

    session_pool.retry_operation_sync(update)

def save_pdf_url(task_id, url):
    def update(session):
        session.execute(
            """
            DECLARE $task_id AS String;
            DECLARE $pdf_url AS String;

            UPDATE lecture_tasks
            SET pdf_url = $pdf_url
            WHERE task_id = $task_id;
            """,
            {"$task_id": task_id, "$pdf_url": url},
            commit_tx=True
        )

    session_pool.retry_operation_sync(update)

def update_error(task_id, message):
    def update(session):
        session.execute(
            """
            DECLARE $task_id AS String;
            DECLARE $status AS String;
            DECLARE $error_message AS String;

            UPDATE lecture_tasks
            SET status = $status, error_message = $error_message
            WHERE task_id = $task_id;
            """,
            {
                "$task_id": task_id,
                "$status": "ERROR",
                "$error_message": message
            },
            commit_tx=True
        )

    session_pool.retry_operation_sync(update)

# -----------------------------
# Yandex Disk
# -----------------------------
def validate_disk_link(public_url):
    resp = requests.get(
        "https://cloud-api.yandex.net/v1/disk/public/resources",
        params={"public_key": public_url},
        headers={"Authorization": f"OAuth {DISK_API_TOKEN}"}
    )

    if resp.status_code != 200:
        raise Exception("Invalid Yandex Disk link")

    return resp.json()

def download_file(download_url):
    r = requests.get(download_url, stream=True)
    if r.status_code != 200:
        raise Exception("Failed to download video")

    fd, path = tempfile.mkstemp(suffix=".mp4")
    with os.fdopen(fd, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

    return path

# -----------------------------
# PDF
# -----------------------------
def generate_pdf(title, text):
    fd, path = tempfile.mkstemp(suffix=".pdf")
    c = canvas.Canvas(path, pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 800, title)

    c.setFont("Helvetica", 11)
    y = 760
    for line in text.split("\n"):
        c.drawString(50, y, line)
        y -= 14
        if y < 50:
            c.showPage()
            y = 800

    c.save()
    return path

# -----------------------------
# Object Storage
# -----------------------------
def upload_pdf(task_id, path):
    key = f"{task_id}.pdf"

    s3.upload_file(
        path,
        BUCKET_NAME,
        key
    )

    return f"https://storage.yandexcloud.net/{BUCKET_NAME}/{key}"
