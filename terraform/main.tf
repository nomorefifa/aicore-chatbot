terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # 상태 파일을 GCS에 저장 (팀 공유 / 충돌 방지)
  backend "gcs" {
    bucket = "aicore-tfstate"   # var 사용 불가 → terraform.tfvars로 override 불가, 직접 입력
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
