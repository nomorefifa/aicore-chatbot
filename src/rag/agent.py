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

    "■ STEP 4. 커리큘럼 생성 (generate_curriculum 도구 사용)\n"
    "  STEP 1~3에서 수집한 모든 정보를 정리하여 generate_curriculum 도구에 전달하세요.\n"
    "  이 도구는 전용 모델을 사용하여 고품질 커리큘럼을 생성합니다.\n"
    "  context에 반드시 포함할 내용:\n"
    "    [요구사항] 교육 분야, 대상, 시간, 수준, 이론/실습 구성, 목적\n"
    "    [DB 참고] search_curriculum/get_curriculum_detail 결과 (있는 경우)\n"
    "    [웹 참고] web_search 결과 (사용한 경우)\n"
    "  generate_curriculum이 반환한 결과를 사용자에게 그대로 전달하세요.\n"
    "  직접 커리큘럼을 작성하지 말고, 반드시 generate_curriculum 도구를 사용하세요.\n\n"

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
            use_weaviate = os.getenv("USE_WEAVIATE", "false").lower() == "true"
            if use_weaviate:
                from src.embedding.weaviate_embedder import WeaviateEmbeddingStore
                resume_store     = WeaviateEmbeddingStore(collection_name=resume_collection)
                curriculum_store = WeaviateEmbeddingStore(collection_name=curriculum_collection)
                logger.info("로컬 모드: Weaviate (이력서 + 커리큘럼) + Gemini 웹검색")
            else:
                from src.embedding.embedder import EmbeddingStore
                resume_store     = EmbeddingStore(collection_name=resume_collection,     db_dir=db_dir)
                curriculum_store = EmbeddingStore(collection_name=curriculum_collection, db_dir=db_dir)
                logger.info("로컬 모드: ChromaDB (이력서 + 커리큘럼) + Gemini 웹검색")
            tools = get_tools(resume_store=resume_store, curriculum_store=curriculum_store)

        self.memory = MemorySaver()
        system_prompt = _build_system_prompt()
        self.agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt,
            checkpointer=self.memory,
        )

        logger.info(f"Agent 준비 완료 | 날짜: {date.today()} | 모델: {model} | 도구: {[t.name for t in tools]}")

    def ask(self, question: str, thread_id: str = "default", max_retries: int = 2) -> str:
        """질문을 받아 Agent 실행 후 최종 답변 반환. 빈 답변 시 자동 재시도."""
        logger.info(f"질문 [{thread_id}]: {question}")
        config = {"configurable": {"thread_id": thread_id}}

        for attempt in range(max_retries + 1):
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

            answer = self._extract_answer(messages[-1].content)

            if answer.strip():
                logger.info(f"답변 [{thread_id}]: {answer[:200]}")
                return answer

            if attempt < max_retries:
                logger.warning(f"빈 답변 감지 (시도 {attempt + 1}/{max_retries + 1}), 재시도합니다.")
            else:
                logger.warning(f"빈 답변 — 재시도 {max_retries}회 모두 실패")

        return "죄송합니다. 일시적으로 답변을 생성하지 못했습니다. 다시 질문해 주세요."

    @staticmethod
    def _extract_answer(content) -> str:
        """LLM 응답에서 텍스트를 추출. thinking 블록 등 비텍스트 블록 대응."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                    parts.append(block["text"])
            return "\n".join(parts)
        return str(content) if content else ""

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
