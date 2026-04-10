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
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from src.rag.tools import get_tools

load_dotenv(override=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = SystemMessage(content=(
    "당신은 아이코어 내부 교육 관리 시스템입니다.\n"
    "다음 두 가지 주요 기능을 제공합니다:\n\n"

    "【강사 검색】\n"
    "DB에는 각 강사의 이름, 연락처, 이메일, 학력, 경력, 강의이력, 자격증, 전문분야가 저장되어 있습니다.\n"
    "강사 관련 질문은 반드시 search_instructor, get_instructor_detail 등의 도구로 DB를 먼저 조회하세요.\n\n"

    "【커리큘럼 생성/추천】\n"
    "교육 대상(초중고/대학생/기업 등), 분야, 시간(160H/80H 등)이 주어지면 커리큘럼을 생성합니다.\n"
    "반드시 다음 순서로 진행하세요:\n"
    "  1. search_curriculum으로 기존 유사 커리큘럼을 먼저 검색\n"
    "  2. 검색 결과가 충분하면 → 바로 커리큘럼 생성\n"
    "  3. 최신 기술(2024년 이후) 관련이거나 DB 결과가 부족하면 → web_search로 보완 후 생성\n"
    "생성된 커리큘럼은 주차별 또는 모듈별로 구조화하여 제공하세요.\n\n"

    "【공통 규칙】\n"
    "- 반드시 도구를 먼저 사용한 후 답변하세요. 도구 없이 추측하지 마세요.\n"
    "- 도구를 사용해도 데이터가 없는 경우에만 '확인되지 않습니다'라고 답하세요."
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
        self.agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=SYSTEM_PROMPT,
            checkpointer=self.memory,
        )

        logger.info(f"Agent 준비 완료 | 모델: {model} | 도구: {[t.name for t in tools]}")

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
