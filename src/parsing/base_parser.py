"""
범용 문서 파서

텍스트 추출(포맷별 자동 분기) + Gemini 구조화(모델/프롬프트 주입) 조합.

새 문서 타입 추가 시:
  1. models/ 에 모델 추가
  2. prompts.py 에 프롬프트 추가
  3. chunkers/ 에 청커 추가
  4. parse_only_exe.py / embed_only_exe.py 의 DOC_TYPE_CONFIG 에 등록

사용 예시:
  parser = DocumentParser(ResumeData, RESUME_PARSE_PROMPT)
  result = parser.parse(Path("강사이력서.pdf"))

  parser = DocumentParser(CurriculumData, CURRICULUM_PARSE_PROMPT)
  result = parser.parse(Path("커리큘럼.hwp"))
"""

import logging
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DocumentParser:
    """
    파일 포맷에 무관하게 동작하는 범용 파서.

    - 텍스트 추출: .hwp/.hwpx/.pdf/.docx 자동 분기
    - 구조화: 주입된 model_class + prompt_template 으로 Gemini 호출
    """

    SUPPORTED_FORMATS = {'.docx', '.pdf', '.hwp', '.hwpx'}

    def __init__(
        self,
        model_class: type[BaseModel],
        prompt_template: str,
        llm_model: str = "gemini-2.5-flash",
    ):
        self.model_class = model_class
        self.prompt_template = prompt_template
        llm = ChatGoogleGenerativeAI(model=llm_model, temperature=0)
        self.structured_llm = llm.with_structured_output(model_class)

    _OLE2_MAGIC = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

    def _detect_format(self, file_path: Path) -> str:
        """확장자가 잘못된 경우를 대비해 magic bytes로 실제 포맷 감지."""
        suffix = file_path.suffix.lower()
        if suffix == '.docx':
            with open(file_path, 'rb') as f:
                header = f.read(8)
            if header == self._OLE2_MAGIC:
                return '.hwp'
        return suffix

    def extract_text(self, file_path: Path) -> str:
        suffix = self._detect_format(file_path)
        if suffix in ('.hwp', '.hwpx'):
            from .hwp_parser import extract_text as hwp_extract
            return hwp_extract(file_path, force_hwp=True)
        elif suffix == '.pdf':
            from .pdf_parser import extract_text
            return extract_text(file_path)
        elif suffix == '.docx':
            from .docx_parser import extract_text
            return extract_text(file_path)
        raise ValueError(f"지원하지 않는 파일 형식: {suffix}")

    def parse(self, file_path: Path) -> BaseModel | None:
        file_path = Path(file_path)
        try:
            raw_text = self.extract_text(file_path)
            if not raw_text.strip():
                logger.warning(f"텍스트 추출 결과 없음: {file_path.name}")
                return None
            result = self.structured_llm.invoke(
                self.prompt_template.format(text=raw_text)
            )
            logger.info(f"파싱 완료: {file_path.name}")
            return result
        except Exception as e:
            logger.error(f"파싱 실패: {file_path.name} → {e}")
            return None
