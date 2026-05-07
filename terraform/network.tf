# ── VPC / 서브넷 ──────────────────────────────────────────────────────────────

resource "google_compute_network" "vpc" {
  name                    = "aicore-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "private" {
  name                     = "aicore-private-subnet"
  ip_cidr_range            = "10.0.1.0/24"
  region                   = var.region
  network                  = google_compute_network.vpc.id
  private_ip_google_access = true  # Cloud Storage / API 접근 (NAT 없이)
}

# VPC Connector (Cloud Run → VPC 내부 VM 통신)
resource "google_vpc_access_connector" "connector" {
  name          = "aicore-vpc-connector"
  region        = var.region
  network       = google_compute_network.vpc.name
  ip_cidr_range = "10.8.0.0/28"
  min_instances = 2
  max_instances = 3
}

# ── 방화벽 ────────────────────────────────────────────────────────────────────

# Cloud Run → Weaviate (8080) / Neo4j (7687)
resource "google_compute_firewall" "allow_internal" {
  name    = "aicore-allow-internal"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["8080", "7687", "7474"]
  }

  source_ranges = ["10.0.0.0/8", "10.8.0.0/28"]
  target_tags   = ["aicore-vm"]
}

# IAP SSH (개발/운영 접속용)
resource "google_compute_firewall" "allow_iap_ssh" {
  name    = "aicore-allow-iap-ssh"
  network = google_compute_network.vpc.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]  # Google IAP 고정 대역
  target_tags   = ["aicore-vm"]
}
