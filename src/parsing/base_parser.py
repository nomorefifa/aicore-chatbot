"""
파서 공통 요소: 프롬프트, 청킹 로직, JSON → 청크 변환
모든 파서(docx / pdf / hwp)가 공유합니다.
"""

import logging
from pathlib import Path

from .models import Chunk, ResumeData

logger = logging.getLogger(__name__)

PARSE_PROMPT = """아래는 강사 이력서 원문 텍스트입니다.
내용을 분석하여 주어진 스키마에 맞게 구조화하세요.
형식이 불규칙하거나 항목이 누락된 경우 판단하여 최대한 채워 넣고, 알 수 없는 항목은 null로 두세요.

=== 이력서 텍스트 ===
{resume_text}
"""


class ResumeChunker:
    """
    ResumeData를 섹션별 청크로 분할.

    청킹 전략:
    - 프로필 청크: 강사명 + 전문분야 + 연락처 (개요 검색용)
    - 학력 청크: 학력 전체를 하나의 청크로
    - 경력 청크: 경력 전체를 하나의 청크로
    - 강의이력 청크: 항목당 1개 (핵심 검색 대상)
    - 자격증 청크: 자격증 전체를 하나의 청크로

    각 청크 content 형식: "강사: {name} | 섹션: {section} | {내용}"
    """

    def chunk(self, resume: ResumeData, file_name: str) -> list[Chunk]:
        chunks = []
        base_meta = {
            "instructor_name": resume.instructor_name,
            "file_name": file_name,
            "doc_type": "강사이력서",
        }

        # 1. 프로필 청크
        profile_parts = [f"강사명: {resume.instructor_name}"]
        if resume.phone:
            profile_parts.append(f"연락처: {resume.phone}")
        if resume.email:
            profile_parts.append(f"이메일: {resume.email}")
        if resume.expertise:
            profile_parts.append(f"전문분야: {', '.join(resume.expertise)}")
        if resume.summary:
            profile_parts.append(f"소개: {resume.summary}")

        chunks.append(Chunk(
            content=self._build_content(resume.instructor_name, "프로필", " | ".join(profile_parts)),
            metadata={**base_meta, "section": "프로필"},
        ))

        # 2. 학력 청크
        if resume.education:
            edu_lines = []
            for edu in resume.education:
                parts = [edu.school]
                if edu.major:
                    parts.append(edu.major)
                if edu.degree:
                    parts.append(edu.degree)
                if edu.graduation_year:
                    parts.append(edu.graduation_year)
                edu_lines.append(" / ".join(parts))

            chunks.append(Chunk(
                content=self._build_content(resume.instructor_name, "학력", "\n".join(edu_lines)),
                metadata={**base_meta, "section": "학력"},
            ))

        # 3. 경력 청크
        if resume.career:
            career_lines = []
            for c in resume.career:
                parts = [c.organization]
                if c.position:
                    parts.append(c.position)
                if c.period:
                    parts.append(c.period)
                if c.description:
                    parts.append(c.description)
                career_lines.append(" / ".join(parts))

            chunks.append(Chunk(
                content=self._build_content(resume.instructor_name, "경력", "\n".join(career_lines)),
                metadata={**base_meta, "section": "경력"},
            ))

        # 4. 강의이력 청크 (항목당 1개)
        for i, t in enumerate(resume.teaching_history):
            parts = [t.organization]
            if t.course_name:
                parts.append(t.course_name)
            if t.period:
                parts.append(t.period)
            if t.hours:
                parts.append(f"{t.hours} 시간")
            if t.description:
                parts.append(t.description)

            chunks.append(Chunk(
                content=self._build_content(resume.instructor_name, "강의이력", " / ".join(parts)),
                metadata={
                    **base_meta,
                    "section": "강의이력",
                    "teaching_organization": t.organization,
                    "course_name": t.course_name or "",
                    "teaching_index": i,
                },
            ))

        # 5. 자격증 청크
        if resume.certifications:
            cert_lines = []
            for cert in resume.certifications:
                parts = [cert.name]
                if cert.issuer:
                    parts.append(cert.issuer)
                if cert.date:
                    parts.append(cert.date)
                cert_lines.append(" / ".join(parts))

            chunks.append(Chunk(
                content=self._build_content(resume.instructor_name, "자격증", "\n".join(cert_lines)),
                metadata={**base_meta, "section": "자격증"},
            ))

        return chunks

    def _build_content(self, name: str, section: str, body: str) -> str:
        return f"강사: {name} | 섹션: {section} | {body}"


def load_chunks_from_parsed(parsed_dir: str | Path = "data/parsed") -> list[Chunk]:
    """
    파싱된 JSON 파일에서 청크 생성 (Gemini 재호출 없음).
    embed_only_exe.py에서 사용.
    """
    parsed_dir = Path(parsed_dir)
    chunker = ResumeChunker()
    all_chunks: list[Chunk] = []

    json_files = list(parsed_dir.glob("*.json"))
    logger.info(f"JSON 파일 {len(json_files)}개에서 청크 생성 시작")

    for json_path in json_files:
        try:
            resume = ResumeData.model_validate_json(json_path.read_text(encoding="utf-8"))
            chunks = chunker.chunk(resume, file_name=json_path.name)
            all_chunks.extend(chunks)
            logger.info(f"{resume.instructor_name}: {len(chunks)}개 청크")
        except Exception as e:
            logger.error(f"청크 생성 실패: {json_path.name} → {e}")

    logger.info(f"총 {len(all_chunks)}개 청크 생성 완료")
    return all_chunks
