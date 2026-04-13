"""
강사 이력서 청킹

섹션별 청크 분할:
  프로필  - 강사명 + 연락처 + 전문분야 (개요 검색용)
  학력    - 학력 전체
  경력    - 경력 전체
  강의이력 - 항목당 1개 (핵심 검색 대상)
  자격증  - 자격증 전체
"""

from src.parsing.models.common import Chunk
from src.parsing.models.resume_models import ResumeData


class ResumeChunker:

    def chunk(self, resume: ResumeData, file_name: str) -> list[Chunk]:
        chunks = []
        base_meta = {
            "instructor_name": resume.instructor_name,
            "file_name": file_name,
            "doc_type": "강사이력서",
        }

        # 1. 프로필
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
            content=self._build(resume.instructor_name, "프로필", " | ".join(profile_parts)),
            metadata={**base_meta, "section": "프로필"},
        ))

        # 2. 학력
        if resume.education:
            lines = []
            for edu in resume.education:
                parts = [edu.school]
                if edu.major:
                    parts.append(edu.major)
                if edu.degree:
                    parts.append(edu.degree)
                if edu.graduation_year:
                    parts.append(edu.graduation_year)
                lines.append(" / ".join(parts))
            chunks.append(Chunk(
                content=self._build(resume.instructor_name, "학력", "\n".join(lines)),
                metadata={**base_meta, "section": "학력"},
            ))

        # 3. 경력
        if resume.career:
            lines = []
            for c in resume.career:
                parts = [c.organization]
                if c.position:
                    parts.append(c.position)
                if c.period:
                    parts.append(c.period)
                if c.description:
                    parts.append(c.description)
                lines.append(" / ".join(parts))
            chunks.append(Chunk(
                content=self._build(resume.instructor_name, "경력", "\n".join(lines)),
                metadata={**base_meta, "section": "경력"},
            ))

        # 4. 강의이력 (항목당 1개)
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
                content=self._build(resume.instructor_name, "강의이력", " / ".join(parts)),
                metadata={
                    **base_meta,
                    "section": "강의이력",
                    "teaching_organization": t.organization,
                    "course_name": t.course_name or "",
                    "teaching_index": i,
                },
            ))

        # 5. 자격증
        if resume.certifications:
            lines = []
            for cert in resume.certifications:
                parts = [cert.name]
                if cert.issuer:
                    parts.append(cert.issuer)
                if cert.date:
                    parts.append(cert.date)
                lines.append(" / ".join(parts))
            chunks.append(Chunk(
                content=self._build(resume.instructor_name, "자격증", "\n".join(lines)),
                metadata={**base_meta, "section": "자격증"},
            ))

        return chunks

    def _build(self, name: str, section: str, body: str) -> str:
        return f"강사: {name} | 섹션: {section} | {body}"
