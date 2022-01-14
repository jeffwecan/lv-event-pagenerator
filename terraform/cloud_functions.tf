locals {
  python_dir    = "${path.module}/../events_page/"
  function_name = "push-webhook-receiver"
  webhook_url   = "https://${var.gcp_region}-${var.gcp_project_id}.cloudfunctions.net/${local.function_name}"

  events_page_env = {
    EVENTS_PAGE_CLOUDFLARE_ZONE    = var.cloudflare_zone
    EVENTS_PAGE_CALENDAR_ID        = var.calendar_id
    EVENTS_PAGE_FOLDER_NAME        = var.gdrive_folder_name
    EVENTS_PAGE_SETTINGS_FILE_NAME = var.gdrive_settings_file_name
    EVENTS_PAGE_GITHUB_REPO        = var.github_repo
    EVENTS_PAGE_HOSTNAME           = google_storage_bucket.static_site.name
    EVENTS_PAGE_SECRET_NAME        = google_secret_manager_secret_version.events_page.name
    EVENTS_PAGE_WEBHOOK_URL        = local.webhook_url
  }
}

resource "local_file" "dotenv" {
  filename = "${path.module}/../events_page/.env"
  content  = join("\n", [for k, v in local.events_page_env : "${k}=${v}"])
}

data "google_storage_bucket" "cloud_functions" {
  name = "gcf-sources-${google_project.events_page.number}-${var.gcp_region}"
}

data "archive_file" "webhook_function" {
  type             = "zip"
  output_file_mode = "0666"
  output_path      = "${path.module}/webhook_function.zip"
  source_dir       = dirname(local_file.dotenv.filename)
}

resource "google_storage_bucket_object" "webhook_archive" {
  name   = "terraform/functions/webhook_${data.archive_file.webhook_function.output_sha}.zip"
  bucket = data.google_storage_bucket.cloud_functions.name
  source = data.archive_file.webhook_function.output_path
}

resource "google_service_account" "webhook_function" {
  account_id   = "webhook"
  display_name = var.page_description
}

resource "google_cloudfunctions_function" "webhook" {
  name        = local.function_name
  description = "Listens for calendar-event-related drive changes"
  runtime     = "python39"

  available_memory_mb   = 128
  max_instances         = 5
  timeout               = 300 # Nice five (5) minute timeout to give GitHub time to pick up our build workflow dispatch, etc.
  service_account_email = google_service_account.webhook_function.email
  source_archive_bucket = data.google_storage_bucket.cloud_functions.name
  source_archive_object = google_storage_bucket_object.webhook_archive.name
  trigger_http          = true
  entry_point           = "process_push_notification"

  environment_variables = local.events_page_env

  build_environment_variables = {
    GOOGLE_FUNCTION_SOURCE = "webhook.py"
  }
}

resource "google_cloudfunctions_function_iam_member" "webhook_allow_all" {
  project        = google_cloudfunctions_function.webhook.project
  region         = google_cloudfunctions_function.webhook.region
  cloud_function = google_cloudfunctions_function.webhook.name

  role   = "roles/cloudfunctions.invoker"
  member = "allUsers"
}
