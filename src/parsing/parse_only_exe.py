"""
문서 파싱 실행 (임베딩 X)

폴더 구조:
  data/raw/{doc_type}/new/    ← 파싱할 파일 여기에 (hwp/pdf/docx 모두 가능)
  data/raw/{doc_type}/done/   ← 파싱 완료 후 자동 이동 (재처리 방지)
  data/parsed/{doc_type}/new/ ← 파싱된 JSON 저장

실행:
  python src/parsing/parse_only_exe.py --doc_type resume
  python src/parsing/parse_only_exe.py --doc_type curriculum

이후:
  data/parsed/{doc_type}/new/ 에서 JSON 확인 → embed_only_exe.py 실행

새 문서 타입 추가 시:
  DOC_TYPE_CONFIG 에 블록 추가만 하면 됨
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv(override=True)

from src.parsing.base_parser import DocumentParser
from src.parsing.models import ResumeData, CurriculumData
from src.parsing.prompts import RESUME_PARSE_PROMPT, CURRICULUM_PARSE_PROMPT

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 새 문서 타입 추가 시 여기에 블록 추가
DOC_TYPE_CONFIG = {
    "resume": {
        "model_class": ResumeData,
        "prompt":      RESUME_PARSE_PROMPT,
        "name_field":  "instructor_name",   # JSON 파일명에 사용할 필드
    },
    "curriculum": {
        "model_class": CurriculumData,
        "prompt":      CURRICULUM_PARSE_PROMPT,
        "name_field":  "course_name",
    },
}

SUPPORTED_FORMATS = {'.docx', '.pdf', '.hwp', '.hwpx'}


def main():
    parser = argparse.ArgumentParser(description="문서 파싱 실행")
    parser.add_argument(
        "--doc_type",
        required=True,
        choices=list(DOC_TYPE_CONFIG.keys()),
        help="파싱할 문서 타입",
    )
    args = parser.parse_args()

    config    = DOC_TYPE_CONFIG[args.doc_type]
    new_dir    = Path(f"data/raw/{args.doc_type}/new")
    done_dir   = Path(f"data/raw/{args.doc_type}/done")
    parsed_dir = Path(f"data/parsed/{args.doc_type}/new")

    done_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    if not new_dir.exists():
        print(f"폴더가 없습니다: {new_dir}")
        print(f"→ 해당 경로에 파일을 추가하세요.")
        return

    files = [f for f in new_dir.iterdir() if f.suffix.lower() in SUPPORTED_FORMATS]
    if not files:
        print(f"새 파일 없음. {new_dir} 에 파일을 추가하세요.")
        return

    logger.info(f"[{args.doc_type}] {len(files)}개 파일 파싱 시작")

    doc_parser = DocumentParser(config["model_class"], config["prompt"])
    name_field = config["name_field"]
    success, fail = 0, 0

    for file_path in files:
        result = doc_parser.parse(file_path)

        if result is None:
            logger.warning(f"파싱 실패: {file_path.name}")
            fail += 1
            continue

        file_stem = getattr(result, name_field, file_path.stem)
        output_path = parsed_dir / f"{file_stem}.json"

        # 동일한 course_name/instructor_name이 이미 있으면 원본 파일명으로 구분
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
    if success:
        print(f"→ data/parsed/{args.doc_type}/new/ 에서 JSON 확인 후 embed_only_exe.py 실행")
    if fail:
        print(f"→ 실패한 파일은 {new_dir} 에 그대로 남아있습니다")


if __name__ == '__main__':
    main()
