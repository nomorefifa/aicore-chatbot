# ── Cloud Run (instructor-agent) ──────────────────────────────────────────────

resource "google_cloud_run_v2_service" "agent" {
  name     = "instructor-agent"
  location = var.region

  template {
    containers {
      image = "asia-northeast3-docker.pkg.dev/${var.project_id}/aicore-chatbot-image/app:latest"

      resources {
        limits = {
          memory = "2Gi"
          cpu    = "1"
        }
      }

      # 환경변수 (민감값은 Secret Manager 참조)
      env {
        name  = "USE_NEO4J"
        value = "true"
      }
      env {
        name  = "NEO4J_URI"
        value = "bolt://${google_compute_instance.weaviate_neo4j.network_interface[0].network_ip}:7687"
      }
      env {
        name  = "NEO4J_USER"
        value = "neo4j"
      }
      env {
        name = "NEO4J_PASSWORD"
        value_source {
          secret_key_ref {
            secret  = "NEO4J_PASSWORD"
            version = "latest"
          }
        }
      }
      env {
        name = "GOOGLE_API_KEY"
        value_source {
          secret_key_ref {
            secret  = "GOOGLE_API_KEY"
            version = "latest"
          }
        }
      }
      env {
        name  = "WEAVIATE_HOST"
        value = google_compute_instance.weaviate_neo4j.network_interface[0].network_ip
      }
    }

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "PRIVATE_RANGES_ONLY"
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    timeout = "300s"

    session_affinity = true
  }
}

# 비인증 접근 허용 (공개 챗봇)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.agent.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
