"""
DOCX 이력서 파싱

흐름: .docx 텍스트 추출 → Gemini 구조화 → ResumeData 반환
"""

import logging
from pathlib import Path

from docx import Document
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from tqdm import tqdm

from .base_parser import PARSE_PROMPT
from .models import ResumeData

load_dotenv()
logger = logging.getLogger(__name__)


class DocxResumeParser:
    def __init__(self, model: str = "gemini-2.5-flash"):
        llm = ChatGoogleGenerativeAI(model=model, temperature=0)
        self.structured_llm = llm.with_structured_output(ResumeData)

    def extract_text(self, file_path: str | Path) -> str:
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

    def parse(self, file_path: str | Path) -> ResumeData | None:
        file_path = Path(file_path)
        try:
            raw_text = self.extract_text(file_path)
            result: ResumeData = self.structured_llm.invoke(
                PARSE_PROMPT.format(resume_text=raw_text)
            )
            logger.info(f"파싱 완료: {file_path.name} → {result.instructor_name}")
            return result
        except Exception as e:
            logger.error(f"파싱 실패: {file_path.name} → {e}")
            return None

    def parse_all(self, raw_dir: str | Path) -> list[tuple[Path, ResumeData]]:
        raw_dir = Path(raw_dir)
        files = list(raw_dir.glob("*.docx"))
        logger.info(f"총 {len(files)}개 DOCX 파일 파싱 시작")

        results = []
        for file_path in tqdm(files, desc="DOCX 파싱"):
            resume = self.parse(file_path)
            if resume is not None:
                results.append((file_path, resume))

        logger.info(f"파싱 완료: {len(results)}/{len(files)}개 성공")
        return results
