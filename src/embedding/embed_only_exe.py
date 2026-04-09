"""
파싱된 JSON → 청킹 → ChromaDB 임베딩 실행

폴더 기반 관리:
  data/parsed/new/  ← 임베딩할 JSON (parse_only_exe.py 실행 후 생성)
  data/parsed/done/ ← 임베딩 완료 후 자동 이동

실행:
  python src/embedding/embed_only_exe.py
"""

import logging
import shutil
import sys
from pathlib import Path

sys.path.insert(0, '.')

from src.parsing.base_parser import ResumeChunker, load_chunks_from_parsed
from src.parsing.models import ResumeData
from src.embedding import EmbeddingStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NEW_DIR  = Path('data/parsed/new')   # 임베딩 대상
DONE_DIR = Path('data/parsed/done')  # 임베딩 완료
DB_DIR   = 'data/vector_db'

DONE_DIR.mkdir(parents=True, exist_ok=True)


def main():
    json_files = list(NEW_DIR.glob('*.json'))

    if not json_files:
        print("임베딩할 JSON 없음. parse_only_exe.py 를 먼저 실행하세요.")
        return

    logger.info(f"임베딩 대상: {len(json_files)}개 JSON")

    chunker = ResumeChunker()
    store = EmbeddingStore(db_dir=DB_DIR)

    for json_path in json_files:
        try:
            resume = ResumeData.model_validate_json(json_path.read_text(encoding='utf-8'))
            chunks = chunker.chunk(resume, file_name=json_path.name)
            store.add(chunks)

            # 임베딩 완료 후 done/으로 이동
            shutil.move(str(json_path), DONE_DIR / json_path.name)
            logger.info(f"완료: {json_path.name} ({len(chunks)}개 청크) → done/으로 이동")

        except Exception as e:
            logger.error(f"실패: {json_path.name} → {e}")

    print(f"\n임베딩 완료. ChromaDB 총 청크 수: {store.count()}")


if __name__ == '__main__':
    main()
