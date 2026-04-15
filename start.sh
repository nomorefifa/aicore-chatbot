#!/bin/bash
set -e

# GCS에서 vector_db 다운로드
echo "GCS에서 vector_db 동기화 중..."
python scripts/sync_vector_db.py

echo "vector_db 디렉토리 내용:"
ls -la data/vector_db/

# 앱 실행
echo "앱 시작..."
python gradio_app.py
