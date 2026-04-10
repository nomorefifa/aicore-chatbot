"""
DOCX 텍스트 추출

python-docx를 사용해 단락과 표를 추출.
텍스트 추출만 담당. 구조화는 DocumentParser(base_parser.py)가 처리.
"""

from pathlib import Path

from docx import Document


def extract_text(file_path: str | Path) -> str:
    """DOCX에서 단락과 표를 추출."""
    doc = Document(str(file_path))
    parts = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            parts.append(text)

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    return "\n".join(parts)
