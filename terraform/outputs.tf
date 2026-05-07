output "cloud_run_url" {
  description = "Cloud Run 서비스 URL"
  value       = google_cloud_run_v2_service.agent.uri
}

output "weaviate_internal_ip" {
  description = "Weaviate/Neo4j VM 내부 IP"
  value       = google_compute_instance.weaviate_neo4j.network_interface[0].network_ip
}

output "vm_schedule_name" {
  description = "VM 스케줄 정책 이름"
  value       = google_compute_resource_policy.vm_schedule.name
}
