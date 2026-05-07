variable "project_id" {
  description = "GCP 프로젝트 ID"
  type        = string
}

variable "region" {
  description = "GCP 리전"
  type        = string
  default     = "asia-northeast3"
}

variable "zone" {
  description = "GCP 존"
  type        = string
  default     = "asia-northeast3-a"
}

variable "neo4j_password" {
  description = "Neo4j 초기 비밀번호"
  type        = string
  sensitive   = true
}

# VM 스케줄 (한국시간 KST = UTC+9)
# Cloud Scheduler는 UTC 기준으로 cron 입력
variable "vm_start_schedule" {
  description = "VM 시작 cron (Asia/Seoul 기준). 기본: 월-금 09:00"
  type        = string
  default     = "0 9 * * 1-5"
}

variable "vm_stop_schedule" {
  description = "VM 중지 cron (Asia/Seoul 기준). 기본: 월-금 19:00"
  type        = string
  default     = "0 19 * * 1-5"
}
