# Terraform 초기 설정 가이드

## 1. 전제 조건

```bash
# Terraform 설치 (Windows: choco install terraform 또는 직접 다운로드)
terraform version  # >= 1.5 확인

# gcloud 인증
gcloud auth application-default login
```

## 2. GCS 상태 버킷 생성 (최초 1회)

```bash
gcloud storage buckets create gs://aicore-tfstate \
  --location=asia-northeast3 \
  --uniform-bucket-level-access
```

## 3. tfvars 작성

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
# terraform.tfvars 파일에 실제 project_id, neo4j_password 입력
```

## 4. 초기화

```bash
cd terraform
terraform init
```

## 5. 기존 리소스 Import (최초 1회)

기존에 수동으로 만든 리소스들을 Terraform 상태로 가져옵니다.

```bash
# PROJECT_ID 환경변수 설정
export PROJECT_ID="your-project-id"
export ZONE="asia-northeast3-a"
export REGION="asia-northeast3"

# VPC
terraform import google_compute_network.vpc projects/$PROJECT_ID/global/networks/aicore-vpc

# 서브넷
terraform import google_compute_subnetwork.private \
  projects/$PROJECT_ID/regions/$REGION/subnetworks/aicore-private-subnet

# VPC Connector
terraform import google_vpc_access_connector.connector \
  projects/$PROJECT_ID/locations/$REGION/connectors/aicore-vpc-connector

# 방화벽
terraform import google_compute_firewall.allow_internal \
  projects/$PROJECT_ID/global/firewalls/aicore-allow-internal
terraform import google_compute_firewall.allow_iap_ssh \
  projects/$PROJECT_ID/global/firewalls/aicore-allow-iap-ssh

# VM (Weaviate + Neo4j)
terraform import google_compute_instance.weaviate_neo4j \
  projects/$PROJECT_ID/zones/$ZONE/instances/weaviate-neo4j-vm

# Cloud Run
terraform import google_cloud_run_v2_service.agent \
  projects/$PROJECT_ID/locations/$REGION/services/instructor-agent
```

> Import 후 `terraform plan`으로 diff 확인 → 의도치 않은 변경이 있으면 .tf 파일을 현재 상태에 맞게 수정

## 6. Plan & Apply

```bash
terraform plan    # 변경 사항 미리보기
terraform apply   # 실제 적용
```

## VM 스케줄 변경

`variables.tf` 또는 `terraform.tfvars`에서 cron 수정:

| 변수 | 의미 | 기본값 (Asia/Seoul) |
|------|------|-------------------|
| `vm_start_schedule` | VM 시작 | 월-금 09:00 |
| `vm_stop_schedule`  | VM 중지 | 월-금 19:00 |

예: 퇴근 시간을 18:00으로 변경 → `vm_stop_schedule = "0 9 * * 1-5"` (KST 18:00 = UTC 09:00)

> `time_zone = "Asia/Seoul"` 이 설정되어 있으므로 cron은 **KST 기준**으로 입력해도 됩니다.
> scheduler.tf의 `time_zone = "Asia/Seoul"` 덕분에 UTC 변환 불필요.
