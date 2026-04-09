"""
HWP / HWPX 이력서 파싱

흐름:
  .hwp  → olefile로 OLE2 바이너리 직접 파싱 → Gemini 구조화
  .hwpx → ZIP 내 XML 파싱 → Gemini 구조화
"""

import logging
import struct
import zipfile
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import olefile
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from tqdm import tqdm

from .base_parser import PARSE_PROMPT
from .models import ResumeData

load_dotenv()

logger = logging.getLogger(__name__)

# HWP 레코드 태그 ID
HWPTAG_PARA_TEXT = 67  # 단락 텍스트


def _is_compressed(ole: olefile.OleFileIO) -> bool:
    """FileHeader에서 본문 압축 여부 확인"""
    if not ole.exists("FileHeader"):
        return True  # 기본값: 압축
    header_data = ole.openstream("FileHeader").read()
    # offset 36: 속성 플래그, bit 1 = 압축여부
    if len(header_data) >= 40:
        flags = struct.unpack_from("<I", header_data, 36)[0]
        return bool(flags & 0x1)
    return True


def _parse_hwp_records(data: bytes) -> str:
    """
    HWP BodyText 레코드 스트림에서 텍스트 추출.
    HWPTAG_PARA_TEXT(67) 레코드의 UTF-16 LE 데이터를 읽는다.
    """
    texts = []
    pos = 0

    while pos + 4 <= len(data):
        header = struct.unpack_from("<I", data, pos)[0]
        tag_id = header & 0x3FF
        size = (header >> 20) & 0xFFF
        pos += 4

        if size == 0xFFF:
            if pos + 4 > len(data):
                break
            size = struct.unpack_from("<I", data, pos)[0]
            pos += 4

        record_data = data[pos: pos + size]
        pos += size

        if tag_id == HWPTAG_PARA_TEXT and size >= 2:
            try:
                text = record_data.decode("utf-16-le", errors="ignore")
                # 제어 문자 제거, 탭/줄바꿈 유지
                cleaned = "".join(
                    c if (ord(c) >= 32 or c in "\t\n") else " "
                    for c in text
                ).strip()
                if cleaned:
                    texts.append(cleaned)
            except Exception:
                pass

    return "\n".join(texts)


def extract_hwp_text(file_path: str | Path) -> str:
    """
    .hwp 파일에서 텍스트 추출 (olefile 직접 파싱)
    pyhwp/LibreOffice 없이 동작.
    """
    file_path = Path(file_path)

    with olefile.OleFileIO(str(file_path)) as ole:
        compressed = _is_compressed(ole)

        # BodyText 섹션 목록 수집 (Section0, Section1, ...)
        sections = sorted(
            entry for entry in ole.listdir()
            if len(entry) == 2 and entry[0] == "BodyText"
        )

        if not sections:
            raise ValueError(f"BodyText 스트림 없음: {file_path.name}")

        all_texts = []
        for section_entry in sections:
            raw = ole.openstream(section_entry).read()
            if compressed:
                try:
                    raw = zlib.decompress(raw, -15)
                except zlib.error:
                    pass  # 압축 안 된 섹션일 수 있음
            section_text = _parse_hwp_records(raw)
            if section_text:
                all_texts.append(section_text)

    return "\n".join(all_texts)


def extract_hwpx_text(file_path: str | Path) -> str:
    """
    .hwpx 파일에서 텍스트 추출 (ZIP + XML 파싱)
    hwpx는 ZIP 컨테이너이므로 라이브러리 불필요.
    """
    texts = []
    with zipfile.ZipFile(file_path) as z:
        section_files = sorted(
            name for name in z.namelist()
            if name.startswith("Contents/section")
        )

        if not section_files:
            raise ValueError(f"hwpx 내 섹션 파일 없음: {file_path}")

        for section_file in section_files:
            with z.open(section_file) as f:
                try:
                    tree = ET.parse(f)
                    for el in tree.iter():
                        if el.text and el.text.strip():
                            texts.append(el.text.strip())
                except ET.ParseError as e:
                    logger.warning(f"XML 파싱 경고 ({section_file}): {e}")

    return "\n".join(texts)


def extract_text(file_path: str | Path) -> str:
    """확장자에 따라 .hwp / .hwpx 텍스트 추출 자동 분기"""
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix == ".hwp":
        return extract_hwp_text(file_path)
    elif suffix == ".hwpx":
        return extract_hwpx_text(file_path)
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {suffix} ({file_path.name})")


class HwpResumeParser:
    """
    HWP/HWPX 이력서 파일을 텍스트 추출 → Gemini 구조화 → ResumeData 반환
    기존 ResumeParser(docx)와 동일한 인터페이스
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        llm = ChatGoogleGenerativeAI(model=model, temperature=0)
        self.structured_llm = llm.with_structured_output(ResumeData)

    def parse(self, file_path: str | Path) -> ResumeData | None:
        file_path = Path(file_path)
        try:
            raw_text = extract_text(file_path)

            if not raw_text:
                logger.warning(f"텍스트 추출 결과 없음: {file_path.name}")
                return None

            logger.info(f"텍스트 추출 완료: {file_path.name} ({len(raw_text)}자)")

            prompt = PARSE_PROMPT.format(resume_text=raw_text)
            result: ResumeData = self.structured_llm.invoke(prompt)
            logger.info(f"파싱 완료: {file_path.name} → {result.instructor_name}")
            return result

        except Exception as e:
            logger.error(f"파싱 실패: {file_path.name} → {e}")
            return None

    def parse_all(self, hwp_dir: str | Path) -> list[tuple[Path, ResumeData]]:
        hwp_dir = Path(hwp_dir)
        files = list(hwp_dir.glob("*.hwp")) + list(hwp_dir.glob("*.hwpx"))
        logger.info(f"총 {len(files)}개 HWP 파일 파싱 시작")

        results = []
        for file_path in tqdm(files, desc="HWP 이력서 파싱"):
            resume = self.parse(file_path)
            if resume is not None:
                results.append((file_path, resume))

        logger.info(f"파싱 완료: {len(results)}/{len(files)}개 성공")
        return results
