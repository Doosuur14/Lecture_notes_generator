resource "yandex_vpc_network" "vpc" {
  name = "${var.prefix}-vpc"
}

resource "yandex_ydb_database_serverless" "lecture_tasks_db" {
  name      = "${var.prefix}-ydb"
  folder_id = var.folder_id
}

resource "yandex_storage_bucket" "pdf_bucket" {
  bucket = "${var.prefix}-pdf"
  acl    = "private"
}

resource "yandex_serverless_container" "api" {
  name   = "${var.prefix}-api"
  memory = 256
  service_account_id = "your-service-account-id"

  image {
    url = "cr.yandex/crp13fp43bp191ee1lt8/api:latest"
  }
}




