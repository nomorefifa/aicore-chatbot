"""
아이코어 내부 RAG Agent (LangGraph ReAct 기반)

지원 기능:
    - 강사 이력서 검색 (ChromaDB: instructor_resumes)
    - 커리큘럼 검색 및 생성 (ChromaDB: curriculum_docs)
    - 최신 트렌드 검색 (Gemini Google Search Grounding)

도구 세트 전환:
    .env에서 USE_GCP_SERVICES=false → ChromaDB 기반 도구 (로컬)
    .env에서 USE_GCP_SERVICES=true  → Vertex AI Search + BigQuery (GCP)

새 도구 추가 시:
    src/rag/tools/chromadb/ → ChromaDB 기반 도구
    src/rag/tools/gcp/      → GCP 서비스 기반 도구
    src/rag/tools/__init__.py의 get_tools()에 등록
"""

import os
import logging
from datetime import date
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from src.rag.tools import get_tools

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _build_system_prompt() -> SystemMessage:
    """에이전트 초기화 시점의 날짜를 주입한 시스템 프롬프트를 생성합니다."""
    today = date.today()
    current_date_str = today.strftime("%Y년 %m월 %d일")
    current_year = today.year

    return SystemMessage(content=(
        f"오늘 날짜: {current_date_str}\n"
        "커리큘럼 생성 시 웹 검색 쿼리에는 반드시 위 날짜 기준 연도를 사용하세요.\n\n"

        "당신은 아이코어 내부 교육 관리 시스템입니다.\n"
        "다음 두 가지 주요 기능을 제공합니다:\n\n"

    # ── 강사 검색 ──
    "【강사 검색】\n"
    "DB에는 각 강사의 이름, 연락처, 이메일, 학력, 경력, 강의이력, 자격증, 전문분야가 저장되어 있습니다.\n"
    "강사 관련 질문은 반드시 search_instructor, get_instructor_detail 등의 도구로 DB를 먼저 조회하세요.\n\n"

    # ── 커리큘럼 생성 ──
    "【커리큘럼 생성/추천】\n\n"

    "■ STEP 1. 필수 정보 확인\n"
    "커리큘럼 생성 요청 시 아래 정보를 반드시 확인하세요.\n"
    "빠진 항목이 하나라도 있으면 커리큘럼을 생성하지 말고 먼저 사용자에게 되물어보세요.\n"
    "  ① 교육 분야 (예: Python, 데이터분석, AI, 클라우드, IoT, LLM 등)\n"
    "  ② 교육 대상 (예: 비전공 대학생, 기업 재직자, 초중고 학생, 전공자 등)\n"
    "  ③ 총 교육 시간 (아이코어 기준 160H이 가장 일반적이며 80H, 40H 과정도 있음, 교육 시간은 프로그램 별로 상이함)\n"
    "  ④ 수준 (초급/중급/고급 — 대상에서 추정 가능하면 추정 후 확인)\n"
    "  ⑤ 이론/실습 구성 — 아래와 같이 질문하세요:\n"
    "     '수업 방식은 어떻게 구성할까요? 예: 이론 위주, 실습 위주, 이론+실습 병행, 프로젝트 중심 등'\n"
    "     사용자가 잘 모르겠다고 하면 DB 검색된 유사 과정의 구성을 안내하고 선택하도록 하세요.\n"
    "  ⑥ 교육 목적 또는 특이사항 (있는 경우만 — 예: 자격증 병행, 취업연계, 지역특화 등)\n\n"

    "■ STEP 2. 기존 커리큘럼 검색\n"
    "  1) search_curriculum으로 유사 커리큘럼을 검색합니다.\n"
    "  2) 유사 과정이 있으면 get_curriculum_detail로 세부 구조(모듈/주차 구성, 시간 배분)를 확인합니다.\n"
    "  3) 기존 과정의 주차 구성, 시간 배분, 주제 흐름, 세부 내용을 골격으로 활용합니다.\n"
    "     특히 기존 과정의 이론/실습 구성 패턴을 참고하세요.\n\n"

    "■ STEP 3. 외부 참고 자료 검색 (web_search 활용)\n"
    "  아래 경우에는 web_search를 적극적으로 활용하세요:\n"
    "  - DB 검색 결과가 없거나 유사한 과정이 부족한 경우\n"
    "  - 최신/신기술 분야 (LLM, 생성형AI, 최신 클라우드 서비스 등)\n"
    "  - 사용자가 최신 트렌드 반영을 요청한 경우\n"
    "  web_search 활용 시 아래 관점으로 검색하세요:\n"
    f"  - '{{분야}} 교육과정 커리큘럼 {{시간}}시간' — 타 기관 유사 과정 참고\n"
    f"  - '{{분야}} 실무 로드맵 {current_year}' — 최신 기술 스택 및 학습 순서\n"
    f"  - '{{분야}} 국비지원 교육과정 {current_year}' — 공개된 타 교육기관 커리큘럼 참고\n"
    "  검색 결과에서 최신 기술 스택, 도구, 커리큘럼 구성 아이디어를 추출하여\n"
    "  기존 DB 자료와 함께 반영합니다.\n\n"

    "■ STEP 4. 커리큘럼 생성 가이드라인\n\n"

    "  [시간 구성 기준]\n"
    "  커리큘럼은 총 시간을 기준으로 내용을 구성합니다.\n"
    "  일정(주 몇 회, 하루 몇 시간 등)은 프로그램마다 다르기 때문에 시스템이 정하지 않습니다.\n"
    "  대신 커리큘럼 생성 후 아래 안내를 반드시 추가하세요:\n"
    "  '※ 일정은 프로그램 운영 방식(예: 주 3회×4H, 매일 8H, 주말 집중 등)에 따라 조정해드릴 수 있습니다.\n"
    "     운영 일정을 알려주시면 해당 일정에 맞게 커리큘럼을 재구성해드리겠습니다.'\n"
    "  커리큘럼 표의 단위는 총 시간을 의미 있는 주제 블록으로 나눠서 작성합니다.\n"
    "  (예: 160H → 8~10개 블록, 80H → 4~6개 블록, 40H → 3~5개 블록)\n"
    "  각 블록의 시간 합계가 총 시간과 정확히 일치하도록 하세요.\n"
    "  후반부에는 반드시 프로젝트 블록을 배치합니다 (총 시간의 10~20%).\n\n"

    "  [주제 흐름]\n"
    "  기존 과정들은 공통적으로 아래 흐름을 따릅니다.\n"
    "  이 순서를 기본으로 하되, 분야와 수준에 맞게 조절하세요.\n"
    "  1. 기초/환경설정 (도구 설치, 개발환경 구축, 기본 개념)\n"
    "  2. 핵심 기술 학습 (분야별 주요 이론과 실습)\n"
    "  3. 응용/심화 (고급 기법, 타 기술 연계, 실무 적용)\n"
    "  4. 프로젝트 (팀 또는 개인 프로젝트, 결과 발표)\n"
    "  초급 과정은 1단계에 충분한 시간을 배분하고,\n"
    "  고급 과정은 1단계를 최소화하고 3~4단계에 집중합니다.\n\n"

    "  [교육 대상별 고려사항]\n"
    "  - 비전공자/입문자: 용어 설명 포함, 따라하기 실습 위주, 취업 포트폴리오 프로젝트 고려\n"
    "  - 전공자/개발자: 기초 축소, 심화 확대, 현업 도구/프레임워크 활용\n"
    "  - 기업 재직자: 업무 즉시 적용 가능한 실무 예제 중심\n"
    "  - 초중고 학생: 쉬운 용어, 흥미 유발 요소(게임/시각화 등), 짧은 단위 실습\n\n"

    "■ STEP 5. 출력 형식\n"
    "아래 형식을 반드시 따르세요. 표(|) 형식은 사용하지 마세요. 사용자가 바로 복사하여 쓸 수 있어야 합니다.\n\n"

    "--- 출력 예시 시작 ---\n"
    "과정명: {과정명}\n"
    "교육 대상: {교육 대상}\n"
    "총 교육 시간: {총 시간}H\n"
    "수준: {초급/중급/고급}\n"
    "교육 방식: {사용자가 선택한 이론/실습 구성}\n"
    "교육 목표: {1~2문장}\n"
    "\n"
    "[1단계] {주제명} ({시간}H) - {방법: 이론 / 실습 / 이론+실습 / 프로젝트}\n"
    "  - {세부 내용 항목 1}\n"
    "  - {세부 내용 항목 2}\n"
    "  - {세부 내용 항목 3}\n"
    "\n"
    "[2단계] {주제명} ({시간}H) - {방법}\n"
    "  - {세부 내용 항목 1}\n"
    "  - {세부 내용 항목 2}\n"
    "\n"
    "(모든 단계를 빠짐없이 작성. 각 단계 시간의 합계 = 총 교육 시간)\n"
    "\n"
    "참고한 기존 과정: {DB에서 찾은 과정명 나열}\n"
    "외부 참고 자료: {web_search 결과에서 실제 반영한 내용 요약.\n"
    "  예) '2025 Python 데이터분석 로드맵 기준 최신 라이브러리(Polars 등) 흐름 반영'\n"
    "  예) 'HRD-Net 공개 과정 구조 참고하여 단계별 흐름 보완'\n"
    "  web_search 미사용 시 없음}\n"
    "비고: {선수 지식, 준비물, 자격증 연계 등}\n"
    "\n"
    "※ 일정은 프로그램 운영 방식(예: 주 3회×4H, 매일 8H, 주말 집중 등)에 따라 조정 가능합니다.\n"
    "  운영 일정을 알려주시면 해당 일정에 맞게 커리큘럼을 재구성해드리겠습니다.\n"
    "--- 출력 예시 끝 ---\n\n"

    # ── 공통 규칙 ──
    "【공통 규칙】\n"
    "- 반드시 도구를 먼저 사용한 후 답변하세요. 도구 없이 추측하지 마세요.\n"
    "- 도구를 사용해도 데이터가 없는 경우에만 '확인되지 않습니다'라고 답하세요.\n"
    "- 커리큘럼 생성 시 사용자의 추가 요구(시간 변경, 특정 주제 추가/삭제 등)에 유연하게 대응하세요.\n"
    "- 이전 대화에서 생성한 커리큘럼이 있으면 해당 맥락을 이어서 수정하세요."
))


class ResumeAgent:
    """
    LangGraph ReAct Agent.

    ReAct 패턴 (Reasoning + Acting):
        질문 입력
            → [Reasoning] 어떤 도구를 쓸지 LLM이 판단
            → [Acting]    도구 실행
            → 결과 확인 후 추가 도구 필요하면 반복
            → 최종 답변

    사용 예시:
        agent = ResumeAgent()
        answer = agent.ask("Python 데이터분석 160H 커리큘럼 만들어줘")
        answer = agent.ask("박영준 강사 전체 정보 알려줘")
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        resume_collection: str = "instructor_resumes",
        curriculum_collection: str = "curriculum_docs",
        db_dir: str = "data/vector_db",
    ):
        llm = ChatGoogleGenerativeAI(model=model, temperature=0)

        use_gcp = os.getenv("USE_GCP_SERVICES", "false").lower() == "true"

        if use_gcp:
            tools = get_tools()
            logger.info("GCP 모드: Vertex AI Search + BigQuery")
        else:
            from src.embedding.embedder import EmbeddingStore
            resume_store     = EmbeddingStore(collection_name=resume_collection,     db_dir=db_dir)
            curriculum_store = EmbeddingStore(collection_name=curriculum_collection, db_dir=db_dir)
            tools = get_tools(resume_store=resume_store, curriculum_store=curriculum_store)
            logger.info("로컬 모드: ChromaDB (이력서 + 커리큘럼) + Gemini 웹검색")

        self.memory = MemorySaver()
        system_prompt = _build_system_prompt()
        self.agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt,
            checkpointer=self.memory,
        )

        logger.info(f"Agent 준비 완료 | 날짜: {date.today()} | 모델: {model} | 도구: {[t.name for t in tools]}")

    def ask(self, question: str, thread_id: str = "default") -> str:
        """질문을 받아 Agent 실행 후 최종 답변 반환."""
        logger.info(f"질문 [{thread_id}]: {question}")
        config = {"configurable": {"thread_id": thread_id}}
        result = self.agent.invoke({"messages": [("user", question)]}, config=config)
        messages = result["messages"]

        from langchain_core.messages import HumanMessage
        start_idx = 0
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                start_idx = i + 1
                break

        for msg in messages[start_idx:]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    logger.info(f"  → 도구 호출: {tc['name']} | 입력: {tc['args']}")
            elif hasattr(msg, "name") and msg.name:
                preview = str(msg.content)[:120].replace("\n", " ")
                logger.info(f"  ← 도구 결과 [{msg.name}]: {preview}...")

        answer = messages[-1].content
        if isinstance(answer, list):
            answer = "\n".join(
                block["text"]
                for block in answer
                if isinstance(block, dict) and block.get("type") == "text"
            )
        logger.info(f"답변 [{thread_id}]: {answer[:200]}")
        return answer

    def ask_with_steps(self, question: str, thread_id: str = "default") -> dict:
        """답변과 함께 도구 사용 과정도 반환. 디버깅/UI 표시용."""
        config = {"configurable": {"thread_id": thread_id}}
        result = self.agent.invoke({"messages": [("user", question)]}, config=config)
        messages = result["messages"]

        steps = []
        for msg in messages[1:-1]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    steps.append({"type": "tool_call", "tool": tc["name"], "input": tc["args"]})
            elif hasattr(msg, "name") and msg.name:
                steps.append({"type": "tool_result", "tool": msg.name, "output": str(msg.content)[:300]})

        return {"answer": messages[-1].content, "steps": steps}
