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
from .resume_parser import ResumeChunker, PARSE_PROMPT

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


def run_pdf_pipeline(
    raw_dir: str | Path = "data/raw",
    parsed_dir: str | Path = "data/parsed",
    model: str = "gemini-2.5-flash",
) -> list[Chunk]:
    """
    PDF 전체 파이프라인 실행:
    data/raw/*.pdf → 파싱 → 청킹 → data/parsed/{강사명}.json 저장 → 청크 목록 반환

    청킹/저장 로직은 기존 resume_parser.py와 동일하게 ResumeChunker 재사용
    """
    raw_dir = Path(raw_dir)
    parsed_dir = Path(parsed_dir)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    parser = PDFResumeParser(model=model)
    chunker = ResumeChunker()

    parse_results = parser.parse_all(raw_dir)

    all_chunks: list[Chunk] = []
    for file_path, resume in parse_results:
        # 파싱 결과 JSON 저장 (docx와 같은 폴더에 저장 → 통합 관리)
        output_path = parsed_dir / f"{resume.instructor_name}.json"
        output_path.write_text(
            resume.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        chunks = chunker.chunk(resume, file_name=file_path.name)
        all_chunks.extend(chunks)
        logger.info(f"{resume.instructor_name}: {len(chunks)}개 청크 생성")

    logger.info(f"PDF 파이프라인 완료 | 총 {len(all_chunks)}개 청크")
    return all_chunks
