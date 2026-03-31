"""
DOCX 이력서 파싱 + 임베딩 실행 스크립트

실행 전 준비:
  - data/raw_new/ 폴더에 새 DOCX 파일들을 복사
  - 이세미 재파싱이 필요하면 data/raw/강사이력서_이세미.docx 도 함께 복사

실행:
  python test/docx_parser_exe.py

주의:
  - raw_new/ 폴더의 파일만 파싱 (기존 data/raw/ 의 25개 파일 재파싱 없음)
  - 이미 data/parsed/ 에 같은 강사명 JSON이 있으면 덮어씀
  - ChromaDB는 ID 기반 upsert → 중복 없음
"""

import sys
sys.path.insert(0, '.')

from src.parsing import run_pipeline
from src.embedding import EmbeddingStore

RAW_NEW_DIR = 'data/raw_new'
PARSED_DIR  = 'data/parsed'
DB_DIR      = 'data/vector_db'

chunks = run_pipeline(
    raw_dir=RAW_NEW_DIR,
    parsed_dir=PARSED_DIR,
)

store = EmbeddingStore(
    collection_name='instructor_resumes',
    db_dir=DB_DIR,
)
store.add(chunks)
print(f"완료. DB 총 청크 수: {store.count()}")
