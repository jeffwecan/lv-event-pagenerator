# data "google_billing_account" "events_page" {
#   display_name = var.gcp_billing_account_name
#   open         = true
# }


resource "google_project" "events_page" {
  name            = var.gcp_project_name
  project_id      = var.gcp_project_id
  billing_account = var.billing_account_id
  # billing_account = data.google_billing_account.events_page.id
}

resource "google_project_service" "events_page" {
  for_each = toset(var.enabled_gcp_services)

  service                    = each.value
  disable_dependent_services = true

  timeouts {
    create = "30m"
    update = "40m"
  }

}

resource "google_app_engine_application" "schedule_app" {
  #  project     = "${var.project_id}"
  location_id = "us-central" ## TODO: data source?
}
