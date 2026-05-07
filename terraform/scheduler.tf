# ── VM 스케줄 자동 시작/중지 (현재 비활성화 - 수동 운영 중) ──────────────────
# 활성화하려면 아래 주석을 해제하고 terraform apply
# 주의: 먼저 terraform plan으로 의도치 않은 변경 없는지 확인

# resource "google_compute_resource_policy" "vm_schedule" {
#   name   = "aicore-vm-schedule"
#   region = var.region
#
#   instance_schedule_policy {
#     vm_start_schedule {
#       schedule = var.vm_start_schedule   # 기본: 월-금 09:00 KST
#     }
#     vm_stop_schedule {
#       schedule = var.vm_stop_schedule    # 기본: 월-금 19:00 KST
#     }
#     time_zone = "Asia/Seoul"
#   }
# }
#
# resource "google_compute_instance_iam_member" "scheduler_sa_weaviate" {
#   project       = var.project_id
#   zone          = var.zone
#   instance_name = google_compute_instance.weaviate_neo4j.name
#   role          = "roles/compute.instanceAdmin.v1"
#   member        = "serviceAccount:service-${data.google_project.project.number}@compute-system.iam.gserviceaccount.com"
# }
#
# resource "google_compute_resource_policy_attachment" "weaviate_schedule" {
#   name            = google_compute_instance.weaviate_neo4j.name
#   zone            = var.zone
#   resource_policy = google_compute_resource_policy.vm_schedule.self_link
# }
#
# data "google_project" "project" {
#   project_id = var.project_id
# }
