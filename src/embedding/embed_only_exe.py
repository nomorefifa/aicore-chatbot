"""
파싱된 JSON → 청킹 → 임베딩 저장

로컬 모드:
  data/parsed/{doc_type}/new/  ← 임베딩할 JSON
  data/parsed/{doc_type}/done/ ← 임베딩 완료 후 자동 이동

GCS 모드 (--gcs_bucket 지정 시):
  gs://{bucket}/parsed/{doc_type}/done/ ← 임베딩할 JSON
  로컬 /tmp/ 를 임시 작업 디렉토리로 사용

실행:
  python src/embedding/embed_only_exe.py --doc_type resume --backend weaviate
  python src/embedding/embed_only_exe.py --doc_type resume --backend weaviate --gcs_bucket aicore-chatbot-public

새 문서 타입 추가 시:
  DOC_TYPE_CONFIG 에 블록 추가만 하면 됨
"""

import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '.')

from src.parsing.models import ResumeData, CurriculumData
from src.parsing.chunkers import ResumeChunker, CurriculumChunker
from src.embedding import EmbeddingStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_DIR = 'data/vector_db'

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


def load_store(backend: str, collection: str):
    if backend == "weaviate":
        from src.embedding.weaviate_embedder import WeaviateEmbeddingStore
        return WeaviateEmbeddingStore(collection_name=collection)
    return EmbeddingStore(collection_name=collection, db_dir=DB_DIR)


def embed_files(json_files: list[Path], config: dict, store, done_dir: Path | None = None):
    model_class = config["model_class"]
    chunker     = config["chunker"]
    success, fail = 0, 0

    for json_path in json_files:
        try:
            data   = model_class.model_validate_json(json_path.read_text(encoding='utf-8'))
            chunks = chunker.chunk(data, file_name=json_path.name)
            store.add(chunks)
            if done_dir:
                shutil.move(str(json_path), done_dir / json_path.name)
            logger.info(f"완료: {json_path.name} ({len(chunks)}개 청크)")
            success += 1
        except Exception as e:
            logger.error(f"실패: {json_path.name} → {e}")
            fail += 1

    return success, fail


def main():
    parser = argparse.ArgumentParser(description="JSON → 임베딩 저장")
    parser.add_argument("--doc_type", required=True, choices=list(DOC_TYPE_CONFIG.keys()))
    parser.add_argument("--backend", choices=["chroma", "weaviate"], default="chroma")
    parser.add_argument("--gcs_bucket", default=None, help="GCS 버킷명 (예: aicore-chatbot-public)")
    args = parser.parse_args()

    config = DOC_TYPE_CONFIG[args.doc_type]
    store  = load_store(args.backend, config["collection"])

    if args.gcs_bucket:
        gcs_parsed = f"gs://{args.gcs_bucket}/parsed/{args.doc_type}/done/"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            subprocess.run(["gsutil", "-m", "cp", f"{gcs_parsed}*.json", str(tmp_dir)], check=True)
            json_files = list(tmp_dir.glob("*.json"))

            if not json_files:
                print(f"임베딩할 JSON 없음: {gcs_parsed}")
                return

            logger.info(f"[{args.doc_type}] 임베딩 대상: {len(json_files)}개 JSON | 백엔드: {args.backend} | GCS 모드")
            success, fail = embed_files(json_files, config, store)

    else:
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

        logger.info(f"[{args.doc_type}] 임베딩 대상: {len(json_files)}개 JSON | 백엔드: {args.backend} | 로컬 모드")
        success, fail = embed_files(json_files, config, store, done_dir)

    print(f"\n임베딩 결과: 성공 {success}개 / 실패 {fail}개")
    print(f"[{args.backend}] [{config['collection']}] 총 청크 수: {store.count()}")


if __name__ == '__main__':
    main()
