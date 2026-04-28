"""
HWP / HWPX 텍스트 추출

흐름:
  .hwp  → olefile로 OLE2 바이너리 직접 파싱 → 텍스트
  .hwpx → ZIP 내 XML 파싱 → 텍스트

텍스트 추출만 담당. 구조화는 DocumentParser(base_parser.py)가 처리.
"""

import logging
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

import olefile

logger = logging.getLogger(__name__)

HWPTAG_PARA_TEXT = 67


def _is_compressed(ole: olefile.OleFileIO) -> bool:
    if not ole.exists("FileHeader"):
        return True
    header_data = ole.openstream("FileHeader").read()
    if len(header_data) >= 40:
        flags = struct.unpack_from("<I", header_data, 36)[0]
        return bool(flags & 0x1)
    return True


def _parse_hwp_records(data: bytes) -> str:
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
    """.hwp 파일에서 텍스트 추출 (olefile 직접 파싱)"""
    file_path = Path(file_path)
    with olefile.OleFileIO(str(file_path)) as ole:
        compressed = _is_compressed(ole)
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
                    pass
            section_text = _parse_hwp_records(raw)
            if section_text:
                all_texts.append(section_text)

    return "\n".join(all_texts)


def extract_hwpx_text(file_path: str | Path) -> str:
    """.hwpx 파일에서 텍스트 추출 (ZIP + XML 파싱)"""
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


def extract_text(file_path: str | Path, force_hwp: bool = False) -> str:
    """확장자에 따라 .hwp / .hwpx 텍스트 추출 자동 분기.
    force_hwp=True 이면 확장자에 상관없이 OLE2 .hwp 형식으로 파싱."""
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    if force_hwp or suffix == ".hwp":
        return extract_hwp_text(file_path)
    elif suffix == ".hwpx":
        return extract_hwpx_text(file_path)
    raise ValueError(f"지원하지 않는 파일 형식: {suffix} ({file_path.name})")
