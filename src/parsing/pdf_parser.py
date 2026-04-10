"""
PDF 텍스트 추출

pdfplumber를 사용해 텍스트와 표를 추출.
텍스트 추출만 담당. 구조화는 DocumentParser(base_parser.py)가 처리.
"""

import logging
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)


def extract_text(file_path: str | Path) -> str:
    """PDF에서 텍스트와 표를 추출."""
    parts = []
    with pdfplumber.open(str(file_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                parts.append(text.strip())

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    cells = [str(cell).strip() for cell in row if cell and str(cell).strip()]
                    if cells:
                        parts.append(" | ".join(cells))

    result = "\n".join(parts)
    if not result.strip():
        logger.warning(f"텍스트 추출 실패 (스캔 PDF일 수 있음): {Path(file_path).name}")
    return result
