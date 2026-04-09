"""
PDF 이력서 파싱 파이프라인

흐름: .pdf 텍스트/표 추출 → Gemini 구조화 (Pydantic) → 섹션별 청킹
기존 resume_parser.py와 동일한 구조, 입력 포맷만 다름
"""

import logging
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from tqdm import tqdm

from .models import Chunk, ResumeData
from .base_parser import ResumeChunker, PARSE_PROMPT

load_dotenv()
logger = logging.getLogger(__name__)


class PDFResumeParser:
    """
    .pdf 이력서 파일을 텍스트 추출 → Gemini 구조화 → ResumeData 반환
    내부 로직은 ResumeParser와 동일, pdfplumber로 텍스트 추출만 다름
    """

    def __init__(self, model: str = "gemini-2.5-flash"):
        llm = ChatGoogleGenerativeAI(model=model, temperature=0)
        self.structured_llm = llm.with_structured_output(ResumeData)

    def extract_text(self, file_path: str | Path) -> str:
        """
        PDF에서 텍스트와 표를 추출.
        - 일반 텍스트: 페이지별 추출
        - 표: 행을 ' | '로 연결 (docx 파서와 동일한 형식)
        """
        parts = []
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                # 일반 텍스트 추출
                text = page.extract_text()
                if text and text.strip():
                    parts.append(text.strip())

                # 표 추출
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        cells = [str(cell).strip() for cell in row if cell and str(cell).strip()]
                        if cells:
                            parts.append(" | ".join(cells))

        return "\n".join(parts)

    def parse(self, file_path: str | Path) -> ResumeData | None:
        """
        단일 .pdf 파일을 파싱하여 ResumeData 반환.
        실패 시 None 반환 후 로깅.
        """
        file_path = Path(file_path)
        try:
            raw_text = self.extract_text(file_path)
            if not raw_text.strip():
                logger.warning(f"텍스트 추출 실패 (스캔 PDF일 수 있음): {file_path.name}")
                return None

            prompt = PARSE_PROMPT.format(resume_text=raw_text)
            result: ResumeData = self.structured_llm.invoke(prompt)
            logger.info(f"파싱 완료: {file_path.name} → {result.instructor_name}")
            return result
        except Exception as e:
            logger.error(f"파싱 실패: {file_path.name} → {e}")
            return None

    def parse_all(self, raw_dir: str | Path) -> list[tuple[Path, ResumeData]]:
        """
        디렉토리 내 모든 .pdf 파일을 일괄 파싱.
        반환: [(파일경로, ResumeData), ...] (실패 파일 제외)
        """
        raw_dir = Path(raw_dir)
        files = list(raw_dir.glob("*.pdf"))
        logger.info(f"총 {len(files)}개 PDF 파일 파싱 시작")

        results = []
        for file_path in tqdm(files, desc="PDF 이력서 파싱"):
            resume = self.parse(file_path)
            if resume is not None:
                results.append((file_path, resume))

        logger.info(f"파싱 완료: {len(results)}/{len(files)}개 성공")
        return results
