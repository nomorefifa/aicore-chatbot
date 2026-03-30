from pydantic import BaseModel, Field
from typing import Optional


class Education(BaseModel):
    """학력"""
    school: str = Field(description="학교명")
    major: Optional[str] = Field(default=None, description="전공")
    degree: Optional[str] = Field(default=None, description="학위 (학사/석사/박사/수료 등)")
    graduation_year: Optional[str] = Field(default=None, description="졸업년도 또는 재학기간")


class Career(BaseModel):
    """경력"""
    organization: str = Field(description="기관 또는 회사명")
    position: Optional[str] = Field(default=None, description="직위 또는 직책")
    period: Optional[str] = Field(default=None, description="근무 기간")
    description: Optional[str] = Field(default=None, description="업무 내용")


class Certification(BaseModel):
    """자격증"""
    name: str = Field(description="자격증명")
    issuer: Optional[str] = Field(default=None, description="발급 기관")
    date: Optional[str] = Field(default=None, description="취득일")


class TeachingHistory(BaseModel):
    """강의이력"""
    organization: str = Field(description="강의 기관명")
    course_name: Optional[str] = Field(default=None, description="과정명 또는 강의명")
    period: Optional[str] = Field(default=None, description="강의 기간")
    hours: Optional[str] = Field(default=None, description="강의 시수 또는 시간")
    description: Optional[str] = Field(default=None, description="강의 내용 또는 특이사항")


class ResumeData(BaseModel):
    """강사 이력서 전체 구조"""
    instructor_name: str = Field(description="강사 이름")
    phone: Optional[str] = Field(default=None, description="연락처")
    email: Optional[str] = Field(default=None, description="이메일")
    education: list[Education] = Field(default_factory=list, description="학력 목록")
    career: list[Career] = Field(default_factory=list, description="경력 목록")
    certifications: list[Certification] = Field(default_factory=list, description="자격증 목록")
    teaching_history: list[TeachingHistory] = Field(default_factory=list, description="강의이력 목록")
    expertise: list[str] = Field(default_factory=list, description="전문분야 키워드 목록")
    summary: Optional[str] = Field(default=None, description="강사 소개 또는 요약")


class Chunk(BaseModel):
    """벡터 DB에 저장할 청크 단위"""
    content: str = Field(description="임베딩할 텍스트 (컨텍스트 prefix 포함)")
    metadata: dict = Field(description="필터링에 사용할 메타데이터")
