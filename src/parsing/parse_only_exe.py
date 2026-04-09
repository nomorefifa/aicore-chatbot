"""
이력서 파싱 실행 (임베딩 X)

폴더 기반 관리:
  data/raw/new/  ← 새 파일 여기에 넣기 (docx / pdf / hwp / hwpx 전부)
  data/raw/done/ ← 파싱 완료 후 자동 이동 (재처리 방지)

실행:
  python src/parsing/parse_only_exe.py

이후:
  data/parsed/ 에서 JSON 확인 → embed_only_exe.py 실행
"""

import logging
import shutil
import sys
from pathlib import Path

sys.path.insert(0, '.')

from src.parsing.docx_parser import DocxResumeParser
from src.parsing.hwp_parser import HwpResumeParser
from src.parsing.pdf_parser import PDFResumeParser
from src.parsing.models import ResumeData

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

NEW_DIR    = Path('data/raw/new')    # 새 파일 보관함
DONE_DIR   = Path('data/raw/done')   # 처리 완료 원본
PARSED_DIR = Path('data/parsed/new')  # 파싱된 JSON (임베딩 전)

DONE_DIR.mkdir(parents=True, exist_ok=True)
PARSED_DIR.mkdir(parents=True, exist_ok=True)

# 확장자 → 파서 매핑
PARSER_MAP = {
    '.docx': DocxResumeParser,
    '.pdf':  PDFResumeParser,
    '.hwp':  HwpResumeParser,
    '.hwpx': HwpResumeParser,
}


def main():
    files = [f for f in NEW_DIR.iterdir() if f.suffix.lower() in PARSER_MAP]

    if not files:
        print(f"새 파일 없음. data/raw/new/ 에 파일을 추가하세요.")
        return

    logger.info(f"새 파일 {len(files)}개 파싱 시작")

    # 파서 인스턴스 캐시 (같은 파서를 여러 번 생성하지 않음)
    parsers: dict = {}

    success, fail = 0, 0

    for file_path in files:
        suffix = file_path.suffix.lower()
        parser_cls = PARSER_MAP[suffix]

        if parser_cls not in parsers:
            parsers[parser_cls] = parser_cls()
        parser = parsers[parser_cls]

        resume: ResumeData | None = parser.parse(file_path)

        if resume is None:
            logger.warning(f"파싱 실패: {file_path.name}")
            fail += 1
            continue

        # JSON 저장
        output_path = PARSED_DIR / f"{resume.instructor_name}.json"
        output_path.write_text(
            resume.model_dump_json(indent=2, ensure_ascii=False),
            encoding='utf-8',
        )

        # 원본 파일을 done/ 으로 이동
        shutil.move(str(file_path), DONE_DIR / file_path.name)
        logger.info(f"완료: {file_path.name} → {output_path.name} (원본: done/으로 이동)")
        success += 1

    print(f"\n파싱 결과: 성공 {success}개 / 실패 {fail}개")
    if success:
        print(f"→ data/parsed/ 에서 JSON 확인 후 embed_only_exe.py 실행")
    if fail:
        print(f"→ 실패한 파일은 data/raw/new/ 에 그대로 남아있습니다")


if __name__ == '__main__':
    main()
