"""
커리큘럼 생성 전용 도구 (Gemini Pro 모델 사용)

Agent(Flash)가 정보 수집(DB 검색, 웹 검색)을 담당하고,
실제 커리큘럼 생성은 이 도구를 통해 Pro 모델에 위임합니다.

흐름:
    Agent(Flash)
        → STEP 1: 사용자에게 필수 정보 확인
        → STEP 2: search_curriculum / get_curriculum_detail 호출
        → STEP 3: web_search 호출 (필요시)
        → STEP 4: generate_curriculum 호출 (수집한 정보 전달 → Pro 모델 생성)
        → Agent(Flash)가 결과를 사용자에게 전달
"""

import os
import logging
from datetime import date
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

CURRICULUM_GEN_MODEL = os.getenv("CURRICULUM_GEN_MODEL", "gemini-2.5-pro")


def _build_curriculum_system_instruction() -> str:
    """커리큘럼 생성 Pro 모델용 시스템 지시문."""
    current_year = date.today().year

    return (
        "당신은 아이코어의 교육 커리큘럼 전문 설계자입니다.\n"
        "주어진 정보(교육 요구사항 + DB 참고 자료 + 웹 검색 결과)를 바탕으로\n"
        "실무에 바로 사용 가능한 고품질 커리큘럼을 생성합니다.\n\n"

        "■ 커리큘럼 생성 가이드라인\n\n"

        "[시간 구성 기준]\n"
        "커리큘럼은 총 시간을 기준으로 내용을 구성합니다.\n"
        "일정(주 몇 회, 하루 몇 시간 등)은 프로그램마다 다르기 때문에 시스템이 정하지 않습니다.\n"
        "커리큘럼 표의 단위는 총 시간을 의미 있는 주제 블록으로 나눠서 작성합니다.\n"
        "(예: 160H → 8~10개 블록, 80H → 4~6개 블록, 40H → 3~5개 블록)\n"
        "각 블록의 시간 합계가 총 시간과 정확히 일치하도록 하세요.\n"
        "후반부에는 반드시 프로젝트 블록을 배치합니다 (총 시간의 10~20%).\n\n"

        "[주제 흐름]\n"
        "기존 과정들은 공통적으로 아래 흐름을 따릅니다.\n"
        "이 순서를 기본으로 하되, 분야와 수준에 맞게 조절하세요.\n"
        "1. 기초/환경설정 (도구 설치, 개발환경 구축, 기본 개념)\n"
        "2. 핵심 기술 학습 (분야별 주요 이론과 실습)\n"
        "3. 응용/심화 (고급 기법, 타 기술 연계, 실무 적용)\n"
        "4. 프로젝트 (팀 또는 개인 프로젝트, 결과 발표)\n"
        "초급 과정은 1단계에 충분한 시간을 배분하고,\n"
        "고급 과정은 1단계를 최소화하고 3~4단계에 집중합니다.\n\n"

        "[교육 대상별 고려사항]\n"
        "- 비전공자/입문자: 용어 설명 포함, 따라하기 실습 위주, 취업 포트폴리오 프로젝트 고려\n"
        "- 전공자/개발자: 기초 축소, 심화 확대, 현업 도구/프레임워크 활용\n"
        "- 기업 재직자: 업무 즉시 적용 가능한 실무 예제 중심\n"
        "- 초중고 학생: 쉬운 용어, 흥미 유발 요소(게임/시각화 등), 짧은 단위 실습\n\n"

        "[참고 자료 활용]\n"
        "- DB 참고 자료가 있으면 주차 구성, 시간 배분, 주제 흐름을 골격으로 활용하세요.\n"
        "- 웹 검색 결과가 있으면 최신 기술 스택, 도구, 트렌드를 반영하세요.\n"
        f"- {current_year}년 기준 최신 기술을 반영하세요.\n\n"

        "■ 출력 형식\n"
        "아래 형식을 반드시 따르세요. 표(|) 형식은 사용하지 마세요.\n"
        "사용자가 바로 복사하여 쓸 수 있어야 합니다.\n\n"

        "과정명: {과정명}\n"
        "교육 대상: {교육 대상}\n"
        "총 교육 시간: {총 시간}H\n"
        "수준: {초급/중급/고급}\n"
        "교육 방식: {사용자가 선택한 이론/실습 구성}\n"
        "교육 목표: {1~2문장}\n\n"

        "[1단계] {주제명} ({시간}H) - {방법: 이론 / 실습 / 이론+실습 / 프로젝트}\n"
        "  - {세부 내용 항목 1}\n"
        "  - {세부 내용 항목 2}\n"
        "  - {세부 내용 항목 3}\n\n"

        "[2단계] {주제명} ({시간}H) - {방법}\n"
        "  - {세부 내용 항목 1}\n"
        "  - {세부 내용 항목 2}\n\n"

        "(모든 단계를 빠짐없이 작성. 각 단계 시간의 합계 = 총 교육 시간)\n\n"

        "참고한 기존 과정: {DB에서 찾은 과정명 나열}\n"
        "외부 참고 자료: {웹 검색 결과에서 실제 반영한 내용 요약. 없으면 '없음'}\n"
        "비고: {선수 지식, 준비물, 자격증 연계 등}\n\n"

        "※ 일정은 프로그램 운영 방식(예: 주 3회×4H, 매일 8H, 주말 집중 등)에 따라 조정 가능합니다.\n"
        "  운영 일정을 알려주시면 해당 일정에 맞게 커리큘럼을 재구성해드리겠습니다.\n\n"

        "■ 규칙\n"
        "- 세부 내용은 구체적으로 작성하세요 (도구명, 라이브러리명, 실습 주제 등)\n"
        "- 각 단계 시간의 합이 총 교육 시간과 정확히 일치해야 합니다\n"
        "- 기존 과정 참고 자료가 있으면 구조를 골격으로 활용하되, 최신 기술을 반영하세요\n"
    )


def get_curriculum_gen_tool() -> list:

    @tool
    def generate_curriculum(context: str) -> str:
        """
        수집한 정보를 바탕으로 고품질 커리큘럼을 생성합니다.
        이 도구는 고성능 Pro 모델을 사용하므로 커리큘럼 최종 생성 시에만 호출하세요.

        STEP 1~3을 통해 수집한 모든 정보를 context에 포함하세요:
        - 사용자 요구사항: 교육 분야, 교육 대상, 총 교육 시간, 수준, 이론/실습 구성, 교육 목적
        - DB 검색 결과: search_curriculum, get_curriculum_detail로 찾은 유사 커리큘럼
        - 웹 검색 결과: web_search로 수집한 최신 트렌드 (사용한 경우)

        context 예시:
        "[요구사항] 분야: Python 데이터분석, 대상: 비전공 대학생, 시간: 160H, 수준: 초급, 구성: 이론+실습 병행, 목적: 취업연계
         [DB 참고] Python 기반 데이터 분석 과정 - 모듈 구성: 1주차 Python 기초(16H)...
         [웹 참고] 2025 데이터분석 트렌드: Pandas 2.0, Polars, DuckDB..."
        """
        from google import genai as google_genai
        from google.genai import types

        client = google_genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        system_instruction = _build_curriculum_system_instruction()

        logger.info(f"커리큘럼 생성 요청 | 모델: {CURRICULUM_GEN_MODEL}")

        response = client.models.generate_content(
            model=CURRICULUM_GEN_MODEL,
            contents=context,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
            ),
        )

        if response.candidates:
            parts = response.candidates[0].content.parts
            texts = [p.text for p in parts if hasattr(p, "text") and p.text]
            result = "\n".join(texts) if texts else "커리큘럼 생성에 실패했습니다."
            logger.info(f"커리큘럼 생성 완료 | 길이: {len(result)}자")
            return result
        return "커리큘럼 생성에 실패했습니다."

    return [generate_curriculum]
