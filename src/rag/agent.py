"""
강사 이력서 RAG Agent (LangGraph ReAct 기반)

RAG 체인과의 차이:
    RAG 체인: 질문 → 검색 1번 → 답변 (흐름 고정)
    Agent   : 질문 → LLM이 도구 선택 → 필요하면 여러 번 검색 → 복잡한 질의 처리

새 문서 유형 추가 시:
    1. src/parsing/{새문서}_parser.py 작성
    2. src/rag/tools/{새문서}_tools.py 작성
    3. 아래 ResumeAgent.__init__에서 tools 목록에 추가
"""

import logging
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from src.embedding.embedder import EmbeddingStore
from src.rag.tools import get_resume_tools

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = SystemMessage(content=(
    "당신은 강사 매칭 전문가입니다. "
    "주어진 도구를 활용해 강사 정보를 검색하고 질문에 답변하세요. "
    "필요하면 여러 도구를 순서대로 사용해도 됩니다. "
    "강사 정보에 없는 내용은 '확인되지 않습니다'라고 답하세요."
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
        store = EmbeddingStore(collection_name=collection_name, db_dir=db_dir)

        # 도구 목록 - 새 문서 유형 추가 시 여기에 추가
        # 예: tools = get_resume_tools(store) + get_lecture_tools(lecture_store)
        tools = get_resume_tools(store)

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
        answer = result["messages"][-1].content
        logger.info("답변 생성 완료")
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
