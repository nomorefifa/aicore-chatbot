from pydantic import BaseModel, Field
from typing import Optional


class CourseModule(BaseModel):
    """과정개요서용 - 모듈 단위 (주제 + 시간)"""
    topic: str = Field(description="주제명")
    subtopics: list[str] = Field(default_factory=list, description="세부 내용 목록")
    hours: Optional[int] = Field(default=None, description="교육 시간")


class WeeklySession(BaseModel):
    """커리큘럼용 - 주차/회차 단위"""
    session_id: str = Field(description="회차 ID (예: 1-1, 2-3)")
    topic: str = Field(description="강의 주제")
    content: str = Field(description="강의 내용")
    method: Optional[str] = Field(default=None, description="강의 방법 (이론 / 실습 / 이론+실습)")
    hours: Optional[int] = Field(default=None, description="강의 시간")


class CurriculumData(BaseModel):
    """교육 과정 문서 구조 (과정개요서 / 커리큘럼 통합)"""
    course_name: str = Field(description="과정명")
    doc_type: str = Field(description="문서 유형: 과정개요서 | 커리큘럼")
    domain: list[str] = Field(default_factory=list, description="도메인 키워드 (AI, 클라우드, 데이터분석 등)")
    target_audience: list[str] = Field(default_factory=list, description="교육 대상 (비전공자, 현직자, 대학생 등)")
    level: Optional[str] = Field(default=None, description="수준: 초급 | 중급 | 고급")
    total_hours: Optional[int] = Field(default=None, description="총 교육 시간")
    objectives: Optional[str] = Field(default=None, description="교육 목표")
    modules: list[CourseModule] = Field(default_factory=list, description="모듈 목록 (과정개요서용)")
    weekly_sessions: list[WeeklySession] = Field(default_factory=list, description="주차별 세부 내용 (커리큘럼용)")
    skills_covered: list[str] = Field(default_factory=list, description="다루는 기술/스킬 목록")
    special_notes: Optional[str] = Field(default=None, description="특이사항 (지역특화, 자격증 병행 등)")
