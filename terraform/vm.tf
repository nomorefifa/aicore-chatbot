# ── Service Account ───────────────────────────────────────────────────────────

resource "google_service_account" "vm_sa" {
  account_id   = "aicore-vm-sa"
  display_name = "Aicore VM Service Account"
}

resource "google_project_iam_member" "vm_sa_storage" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.vm_sa.email}"
}

resource "google_project_iam_member" "vm_sa_artifact" {
  project = var.project_id
  role    = "roles/artifactregistry.reader"
  member  = "serviceAccount:${google_service_account.vm_sa.email}"
}

# ── Weaviate + Neo4j VM ───────────────────────────────────────────────────────

resource "google_compute_instance" "weaviate_neo4j" {
  name         = "weaviate-neo4j-vm"
  machine_type = "e2-standard-2"   # 2vCPU / 8GB
  zone         = var.zone
  tags         = ["aicore-vm"]

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"
      size  = 30  # GB
      type  = "pd-balanced"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.private.id
    # 외부 IP 없음 (Private Only)
  }

  service_account {
    email  = google_service_account.vm_sa.email
    scopes = ["cloud-platform"]
  }

  # 컨테이너 기동 스크립트 (COS: docker compose 플러그인 없음 → 개별 run)
  metadata = {
    startup-script = <<-EOF
      #!/bin/bash
      # Weaviate 이미 실행 중이면 스킵
      if ! docker ps --format '{{.Names}}' | grep -q weaviate; then
        docker run -d \
          --name weaviate \
          --restart unless-stopped \
          -p 8080:8080 \
          -v /home/weaviate_data:/var/lib/weaviate \
          -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
          -e PERSISTENCE_DATA_PATH=/var/lib/weaviate \
          -e DEFAULT_VECTORIZER_MODULE=none \
          semitechnologies/weaviate:1.28.4
      fi

      if ! docker ps --format '{{.Names}}' | grep -q neo4j; then
        docker run -d \
          --name neo4j \
          --restart unless-stopped \
          -p 7474:7474 -p 7687:7687 \
          -v /home/neo4j_data:/data \
          -e NEO4J_AUTH=neo4j/${var.neo4j_password} \
          neo4j:5-community
      fi
    EOF
  }

  # 중지 후 재시작 시 startup-script 재실행
  metadata_startup_script = null

  lifecycle {
    ignore_changes = [
      # 수동으로 VM 중지/시작해도 Terraform이 재생성하지 않도록
      metadata["startup-script"],
    ]
  }
}

# ── 문서 처리 VM (e2-medium, 필요 시 수동 기동) ────────────────────────────

resource "google_compute_instance" "doc_processor" {
  name         = "doc-processor-vm"
  machine_type = "e2-medium"
  zone         = var.zone
  tags         = ["aicore-vm"]

  # 평소에는 중지 상태 유지
  desired_status = "TERMINATED"

  boot_disk {
    initialize_params {
      image = "cos-cloud/cos-stable"
      size  = 20
      type  = "pd-balanced"
    }
  }

  network_interface {
    subnetwork = google_compute_network.vpc.self_link
  }

  service_account {
    email  = google_service_account.vm_sa.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    startup-script = <<-EOF
      #!/bin/bash
      # Artifact Registry 인증
      gcloud auth configure-docker asia-northeast3-docker.pkg.dev --quiet
      # 최신 이미지 pull 후 실행 (필요 시 수동 실행)
      docker pull asia-northeast3-docker.pkg.dev/${var.project_id}/aicore-chatbot-image/app:latest
    EOF
  }
}
