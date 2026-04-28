"""
문서 파싱 실행 (임베딩 X)

로컬 모드:
  data/raw/{doc_type}/new/    ← 파싱할 파일
  data/raw/{doc_type}/done/   ← 파싱 완료 후 자동 이동
  data/parsed/{doc_type}/new/ ← 파싱된 JSON 저장

GCS 모드 (--gcs_bucket 지정 시):
  gs://{bucket}/raw/{doc_type}/  ← 파싱할 파일
  gs://{bucket}/parsed/{doc_type}/done/ ← 파싱된 JSON 저장
  로컬 /tmp/ 를 임시 작업 디렉토리로 사용

실행:
  python src/parsing/parse_only_exe.py --doc_type resume
  python src/parsing/parse_only_exe.py --doc_type resume --gcs_bucket aicore-chatbot-public

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

from dotenv import load_dotenv
load_dotenv(override=True)

from src.parsing.base_parser import DocumentParser
from src.parsing.models import ResumeData, CurriculumData
from src.parsing.prompts import RESUME_PARSE_PROMPT, CURRICULUM_PARSE_PROMPT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DOC_TYPE_CONFIG = {
    "resume": {
        "model_class": ResumeData,
        "prompt":      RESUME_PARSE_PROMPT,
        "name_field":  "instructor_name",
    },
    "curriculum": {
        "model_class": CurriculumData,
        "prompt":      CURRICULUM_PARSE_PROMPT,
        "name_field":  "course_name",
    },
}

SUPPORTED_FORMATS = {'.docx', '.pdf', '.hwp', '.hwpx'}


def gcs_download(gcs_path: str, local_dir: Path) -> list[Path]:
    """GCS 경로에서 파일을 로컬 임시 디렉토리로 다운로드."""
    logger.info(f"GCS 다운로드: {gcs_path} → {local_dir}")
    subprocess.run(["gsutil", "-m", "cp", f"{gcs_path}*", str(local_dir)], check=True)
    return [f for f in local_dir.iterdir() if f.suffix.lower() in SUPPORTED_FORMATS]


def gcs_upload(local_path: Path, gcs_path: str):
    """파싱된 JSON을 GCS에 업로드."""
    subprocess.run(["gsutil", "cp", str(local_path), gcs_path], check=True)
    logger.info(f"GCS 업로드: {local_path.name} → {gcs_path}")


def main():
    parser = argparse.ArgumentParser(description="문서 파싱 실행")
    parser.add_argument("--doc_type", required=True, choices=list(DOC_TYPE_CONFIG.keys()))
    parser.add_argument("--gcs_bucket", default=None, help="GCS 버킷명 (예: aicore-chatbot-public)")
    parser.add_argument("--gcs_path", default=None, help="GCS 커스텀 경로 (예: raw/resume/retry/). --gcs_bucket과 함께 사용")
    args = parser.parse_args()

    config = DOC_TYPE_CONFIG[args.doc_type]
    doc_parser = DocumentParser(config["model_class"], config["prompt"])
    name_field = config["name_field"]
    success, fail = 0, 0

    if args.gcs_bucket:
        gcs_raw = f"gs://{args.gcs_bucket}/{args.gcs_path}" if args.gcs_path else f"gs://{args.gcs_bucket}/raw/{args.doc_type}/"
        gcs_parsed = f"gs://{args.gcs_bucket}/parsed/{args.doc_type}/done/"

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            raw_dir = tmp_dir / "raw"
            parsed_dir = tmp_dir / "parsed"
            raw_dir.mkdir()
            parsed_dir.mkdir()

            files = gcs_download(gcs_raw, raw_dir)
            if not files:
                print(f"GCS에 파싱할 파일 없음: {gcs_raw}")
                return

            logger.info(f"[{args.doc_type}] {len(files)}개 파일 파싱 시작 (GCS 모드)")

            for file_path in files:
                result = doc_parser.parse(file_path)
                if result is None:
                    logger.warning(f"파싱 실패: {file_path.name}")
                    fail += 1
                    continue

                file_stem = getattr(result, name_field, file_path.stem)
                output_path = parsed_dir / f"{file_stem}.json"
                if output_path.exists():
                    output_path = parsed_dir / f"{file_path.stem}.json"
                    logger.warning(f"이름 충돌 → 원본 파일명으로 저장: {output_path.name}")

                output_path.write_text(
                    result.model_dump_json(indent=2, ensure_ascii=False),
                    encoding='utf-8',
                )
                gcs_upload(output_path, f"{gcs_parsed}{output_path.name}")
                logger.info(f"완료: {file_path.name} → {output_path.name}")
                success += 1

    else:
        new_dir    = Path(f"data/raw/{args.doc_type}/new")
        done_dir   = Path(f"data/raw/{args.doc_type}/done")
        parsed_dir = Path(f"data/parsed/{args.doc_type}/new")

        done_dir.mkdir(parents=True, exist_ok=True)
        parsed_dir.mkdir(parents=True, exist_ok=True)

        if not new_dir.exists():
            print(f"폴더가 없습니다: {new_dir}")
            return

        files = [f for f in new_dir.iterdir() if f.suffix.lower() in SUPPORTED_FORMATS]
        if not files:
            print(f"새 파일 없음. {new_dir} 에 파일을 추가하세요.")
            return

        logger.info(f"[{args.doc_type}] {len(files)}개 파일 파싱 시작 (로컬 모드)")

        for file_path in files:
            result = doc_parser.parse(file_path)
            if result is None:
                logger.warning(f"파싱 실패: {file_path.name}")
                fail += 1
                continue

            file_stem = getattr(result, name_field, file_path.stem)
            output_path = parsed_dir / f"{file_stem}.json"
            if output_path.exists():
                output_path = parsed_dir / f"{file_path.stem}.json"
                logger.warning(f"이름 충돌 → 원본 파일명으로 저장: {output_path.name}")

            output_path.write_text(
                result.model_dump_json(indent=2, ensure_ascii=False),
                encoding='utf-8',
            )
            shutil.move(str(file_path), done_dir / file_path.name)
            logger.info(f"완료: {file_path.name} → {output_path.name}")
            success += 1

    print(f"\n파싱 결과: 성공 {success}개 / 실패 {fail}개")
    if fail:
        print("→ 실패한 파일을 확인하세요.")


if __name__ == '__main__':
    main()
