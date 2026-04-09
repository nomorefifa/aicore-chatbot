"""
강사 이력서 RAG Agent (LangGraph ReAct 기반)

RAG 체인과의 차이:
    RAG 체인: 질문 → 검색 1번 → 답변 (흐름 고정)
    Agent   : 질문 → LLM이 도구 선택 → 필요하면 여러 번 검색 → 복잡한 질의 처리

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
    "당신은 아이코어 내부 강사 관리 시스템입니다. "
    "DB에는 각 강사의 이름, 연락처(전화번호), 이메일, 학력, 경력, 강의이력, 자격증, 전문분야 정보가 저장되어 있습니다. "
    "반드시 도구를 먼저 사용하여 DB에서 데이터를 검색한 후 답변하세요. 도구 없이 추측하지 마세요. "
    "검색된 데이터에 있는 연락처, 이메일 등 모든 정보를 그대로 제공하세요. "
    "여러 도구를 순서대로 사용해도 됩니다. "
    "도구를 사용해도 해당 데이터가 없는 경우에만 '확인되지 않습니다'라고 답하세요."
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
        answer = agent.ask("Python이랑 데이터분석 둘 다 가능한 강사 비교해줘")

        result = agent.ask_with_steps("박영준 강사 전체 정보 알려줘")
        print(result['steps'])   # 도구 사용 과정
        print(result['answer'])  # 최종 답변
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        collection_name: str = "instructor_resumes",
        db_dir: str = "data/vector_db",
    ):
        llm = ChatGoogleGenerativeAI(model=model, temperature=0)

        use_gcp = os.getenv("USE_GCP_SERVICES", "false").lower() == "true"
        if use_gcp:
            tools = get_tools()
            logger.info("GCP 모드: Vertex AI Search + BigQuery")
        else:
            from src.embedding.embedder import EmbeddingStore
            store = EmbeddingStore(collection_name=collection_name, db_dir=db_dir)
            tools = get_tools(store)
            logger.info("로컬 모드: ChromaDB")

        # MemorySaver: 세션별 대화기록을 메모리에 유지
        # thread_id가 같으면 같은 대화로 인식, 다르면 독립된 새 대화
        # 서버 재시작 시 초기화됨 (영구 보존 필요 시 SqliteSaver로 교체)
        self.memory = MemorySaver()

        self.agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=SYSTEM_PROMPT,
            checkpointer=self.memory,
        )

        logger.info(f"ResumeAgent 준비 완료 | 모델: {model} | 도구: {[t.name for t in tools]}")

    def ask(self, question: str, thread_id: str = "default") -> str:
        """
        질문을 받아 Agent 실행 후 최종 답변 반환.
        thread_id가 같으면 이전 대화 맥락을 유지함.
        """
        logger.info(f"질문 [{thread_id}]: {question}")
        config = {"configurable": {"thread_id": thread_id}}
        result = self.agent.invoke({"messages": [("user", question)]}, config=config)
        messages = result["messages"]

        # 이번 질문에 해당하는 메시지만 로깅
        # messages에는 전체 대화 히스토리가 담기므로, 마지막 HumanMessage 이후 구간만 순회
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
                preview = msg.content[:120].replace("\n", " ")
                logger.info(f"  ← 도구 결과 [{msg.name}]: {preview}...")

        answer = messages[-1].content
        # Gemini 2.5 Flash는 content를 list of blocks로 반환할 수 있음
        # [{'type': 'text', 'text': '...', 'extras': {'signature': '...'}}]
        # 로그 및 반환값 모두 순수 텍스트로 추출
        if isinstance(answer, list):
            answer = "\n".join(
                block["text"]
                for block in answer
                if isinstance(block, dict) and block.get("type") == "text"
            )
        logger.info(f"답변 [{thread_id}]: {answer}")
        return answer

    def ask_with_steps(self, question: str, thread_id: str = "default") -> dict:
        """
        답변과 함께 도구 사용 과정도 반환.
        디버깅 또는 UI에서 사고과정 표시 시 사용.
        """
        config = {"configurable": {"thread_id": thread_id}}
        result = self.agent.invoke({"messages": [("user", question)]}, config=config)
        messages = result["messages"]

        steps = []
        for msg in messages[1:-1]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    steps.append({
                        "type": "tool_call",
                        "tool": tc["name"],
                        "input": tc["args"]
                    })
            elif hasattr(msg, "name") and msg.name:
                steps.append({
                    "type": "tool_result",
                    "tool": msg.name,
                    "output": msg.content[:300]
                })

        return {"answer": messages[-1].content, "steps": steps}
