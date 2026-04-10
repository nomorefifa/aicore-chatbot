"""
커리큘럼 청킹

섹션별 청크 분할:
  과정개요  - 과정명 + 대상 + 총 시간 + 목표 + 스킬 (개요 검색용)
  모듈      - 모듈별 1개 (과정개요서용)
  주차      - 주차별 묶음 1개 (커리큘럼용)
"""

import json
from src.parsing.models.common import Chunk
from src.parsing.models.curriculum_models import CurriculumData


class CurriculumChunker:

    def chunk(self, curriculum: CurriculumData, file_name: str) -> list[Chunk]:
        chunks = []
        base_meta = {
            "course_name": curriculum.course_name,
            "file_name": file_name,
            "doc_type": curriculum.doc_type,
            "domain": json.dumps(curriculum.domain, ensure_ascii=False),
            "target_audience": json.dumps(curriculum.target_audience, ensure_ascii=False),
            "level": curriculum.level or "",
            "total_hours": curriculum.total_hours or 0,
        }

        # 1. 과정 개요 청크
        overview_parts = [f"과정명: {curriculum.course_name}"]
        if curriculum.total_hours:
            overview_parts.append(f"총 시간: {curriculum.total_hours}H")
        if curriculum.level:
            overview_parts.append(f"수준: {curriculum.level}")
        if curriculum.target_audience:
            overview_parts.append(f"교육대상: {', '.join(curriculum.target_audience)}")
        if curriculum.domain:
            overview_parts.append(f"도메인: {', '.join(curriculum.domain)}")
        if curriculum.skills_covered:
            overview_parts.append(f"다루는 기술: {', '.join(curriculum.skills_covered)}")
        if curriculum.objectives:
            overview_parts.append(f"교육목표: {curriculum.objectives}")
        if curriculum.special_notes:
            overview_parts.append(f"특이사항: {curriculum.special_notes}")

        chunks.append(Chunk(
            content=self._build(curriculum.course_name, "과정개요", " | ".join(overview_parts)),
            metadata={**base_meta, "section": "과정개요"},
        ))

        # 2. 모듈 청크 (과정개요서용)
        for i, module in enumerate(curriculum.modules):
            parts = [f"주제: {module.topic}"]
            if module.hours:
                parts.append(f"시간: {module.hours}H")
            if module.subtopics:
                parts.append(f"내용: {', '.join(module.subtopics)}")

            chunks.append(Chunk(
                content=self._build(curriculum.course_name, "모듈", " | ".join(parts)),
                metadata={
                    **base_meta,
                    "section": "모듈",
                    "module_topic": module.topic,
                    "module_index": i,
                },
            ))

        # 3. 주차 청크 (커리큘럼용) - 같은 주차 세션을 묶어서 1청크
        if curriculum.weekly_sessions:
            week_map: dict[str, list] = {}
            for session in curriculum.weekly_sessions:
                raw = session.session_id.split("-")[0]
                # "1주차", "1회차" 등 숫자 외 문자 제거
                week_num = ''.join(filter(str.isdigit, raw)) or "0"
                week_map.setdefault(week_num, []).append(session)

            for week_num, sessions in sorted(week_map.items(), key=lambda x: int(x[0])):
                lines = []
                for s in sessions:
                    line = f"[{s.session_id}] {s.topic}: {s.content}"
                    if s.method:
                        line += f" ({s.method})"
                    if s.hours:
                        line += f" {s.hours}H"
                    lines.append(line)

                chunks.append(Chunk(
                    content=self._build(curriculum.course_name, f"{week_num}주차", "\n".join(lines)),
                    metadata={
                        **base_meta,
                        "section": "주차",
                        "week_number": int(week_num),
                    },
                ))

        return chunks

    def _build(self, course_name: str, section: str, body: str) -> str:
        return f"과정: {course_name} | 섹션: {section} | {body}"
