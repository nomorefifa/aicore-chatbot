"""
파싱된 JSON → 청킹 → ChromaDB 임베딩

폴더 구조:
  data/parsed/{doc_type}/new/  ← 임베딩할 JSON (parse_only_exe.py 실행 후 생성)
  data/parsed/{doc_type}/done/ ← 임베딩 완료 후 자동 이동

실행:
  python src/embedding/embed_only_exe.py --doc_type resume
  python src/embedding/embed_only_exe.py --doc_type curriculum

새 문서 타입 추가 시:
  DOC_TYPE_CONFIG 에 블록 추가만 하면 됨
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

sys.path.insert(0, '.')

from src.parsing.models import ResumeData, CurriculumData
from src.parsing.chunkers import ResumeChunker, CurriculumChunker
from src.embedding import EmbeddingStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_DIR = 'data/vector_db'

# 새 문서 타입 추가 시 여기에 블록 추가
DOC_TYPE_CONFIG = {
    "resume": {
        "model_class": ResumeData,
        "chunker":     ResumeChunker(),
        "collection":  "instructor_resumes",
    },
    "curriculum": {
        "model_class": CurriculumData,
        "chunker":     CurriculumChunker(),
        "collection":  "curriculum_docs",
    },
}


def main():
    parser = argparse.ArgumentParser(description="JSON → ChromaDB 임베딩")
    parser.add_argument(
        "--doc_type",
        required=True,
        choices=list(DOC_TYPE_CONFIG.keys()),
        help="임베딩할 문서 타입",
    )
    args = parser.parse_args()

    config   = DOC_TYPE_CONFIG[args.doc_type]
    new_dir  = Path(f"data/parsed/{args.doc_type}/new")
    done_dir = Path(f"data/parsed/{args.doc_type}/done")
    done_dir.mkdir(parents=True, exist_ok=True)

    if not new_dir.exists():
        print(f"폴더가 없습니다: {new_dir}")
        return

    json_files = list(new_dir.glob("*.json"))
    if not json_files:
        print(f"임베딩할 JSON 없음. parse_only_exe.py --doc_type {args.doc_type} 를 먼저 실행하세요.")
        return

    logger.info(f"[{args.doc_type}] 임베딩 대상: {len(json_files)}개 JSON")

    model_class = config["model_class"]
    chunker     = config["chunker"]
    store       = EmbeddingStore(collection_name=config["collection"], db_dir=DB_DIR)

    success, fail = 0, 0
    for json_path in json_files:
        try:
            data   = model_class.model_validate_json(json_path.read_text(encoding='utf-8'))
            chunks = chunker.chunk(data, file_name=json_path.name)
            store.add(chunks)
            shutil.move(str(json_path), done_dir / json_path.name)
            logger.info(f"완료: {json_path.name} ({len(chunks)}개 청크) → done/으로 이동")
            success += 1
        except Exception as e:
            logger.error(f"실패: {json_path.name} → {e}")
            fail += 1

    print(f"\n임베딩 결과: 성공 {success}개 / 실패 {fail}개")
    print(f"ChromaDB [{config['collection']}] 총 청크 수: {store.count()}")


if __name__ == '__main__':
    main()
