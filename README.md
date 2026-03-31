# 아이코어 강사 매칭 챗봇

강사 이력서를 벡터DB에 저장하고, 자연어로 강사 정보를 검색할 수 있는 내부 챗봇입니다.

---

## GCP 인프라 구성

```
[GitHub]
    main 브랜치 푸시
        ↓ GitHub Actions 자동 실행
[Artifact Registry]
    Docker 이미지 빌드 & 저장
        ↓ 새 이미지로 배포
[Cloud Run]
    컨테이너 시작 시 GCS에서 vector_db 자동 다운로드
        ↓ 앱 실행
[GCS]
    vector_db (ChromaDB) 파일 별도 보관
```

| 항목 | 값 |
|------|-----|
| 프로젝트 ID | test-icore |
| 리전 | asia-northeast3 (서울) |
| Cloud Run 서비스명 | instructor-agent |
| Artifact Registry | asia-northeast3-docker.pkg.dev/test-icore/aicore-chatbot-image |
| GCS 버킷 | gs://test-icore-vector-db/ |

**코드 변경 시** (기능 추가, 버그 수정 등)
→ dev 브랜치 수정 후 GitHub에서 dev → main PR 머지하면 자동 배포

**강사 데이터 변경 시** (이력서 추가/수정)
→ 로컬에서 파싱 + 임베딩 후 GCS 수동 업로드 (아래 절차 참고)

---

## 사용 방법

챗봇 URL에 접속 후 자연어로 질문합니다.

**강사 검색 및 추천**
```
Python이랑 데이터분석 둘 다 가능한 강사 추천해줘
AI 관련 강의 경험 있는 강사 알려줘
```

**특정 강사 정보 조회**
```
박영준 강사 정보 알려줘
김민주 강사 연락처랑 이메일 알려줘
이세미 강사 학력이랑 경력 알려줘
```

**강사 목록 조회**
```
현재 보유한 강사 리스트 뽑아줘
전체 강사 몇 명이야?
```

**강의이력 검색**
```
삼성 강의 경험 있는 강사 있어?
데이터분석 과정 가르쳐본 강사 찾아줘
```

> DB에 저장된 정보: 이름, 연락처, 이메일, 학력, 경력, 강의이력, 자격증, 전문분야

---

## 새 강사 이력서 추가 절차

> Windows CMD 환경 기준 (conda 환경: `icore-rag`)

### 1단계 — 파일 준비

| 파일 형식 | 추가 위치 |
|-----------|-----------|
| PDF | `data\raw\raw_pdf\` |
| DOCX | `data\raw_new\` |

### 2단계 — 파싱 + 임베딩 실행

**PDF 파일인 경우**
```cmd
conda activate icore-rag
python test\pdf_parser_exe.py
```

**DOCX 파일인 경우**
```cmd
conda activate icore-rag
python test\docx_parser_exe.py
```

- 스캔 PDF(텍스트 추출 불가)는 로그에 "텍스트 추출 실패" 출력 후 자동 스킵
- 스캔 PDF는 OCR 처리 후 DOCX로 변환해서 `data\raw_new\`에 추가
- HWP 파일은 직접 지원 안 됨 → 수동으로 DOCX 변환 후 추가

### 3단계 — GCS 업로드

```cmd
gsutil -m cp -r data\vector_db gs://test-icore-vector-db/
```

기존 GCS 버킷을 로컬 vector_db로 덮어씁니다 (신규 + 기존 데이터 모두 포함).

### 4단계 — Cloud Run 재시작

```cmd
gcloud run services update instructor-agent ^
  --region asia-northeast3 ^
  --update-env-vars REFRESH=%DATE%%TIME%
```

이미지 재빌드 없이 컨테이너만 재시작되며, 시작 시 GCS에서 업데이트된 vector_db를 자동으로 가져옵니다.

---

## 로컬 실행

```cmd
conda activate icore-rag
python gradio_app.py
```

`.env` 파일에 `GOOGLE_API_KEY` 설정 필요.

---

## 브랜치 전략

```
feature/기능명  →  dev (로컬 테스트)  →  main (자동 배포)
```
