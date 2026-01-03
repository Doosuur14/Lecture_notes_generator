

output "pdf_bucket_name" {
  value = yandex_storage_bucket.pdf_bucket.bucket
}

output "ydb_database_name" {
  value = yandex_ydb_database_serverless.lecture_tasks_db.name
}

output "ydb_database_id" {
  value = yandex_ydb_database_serverless.lecture_tasks_db.id
}
