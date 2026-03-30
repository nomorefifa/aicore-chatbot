"""
강사 매칭 챗봇 UI (Gradio)
실행: python app.py

세션 관리:
    gr.Request.session_hash → 브라우저 탭마다 고유한 ID 자동 부여
    같은 탭 = 같은 thread_id = 대화 맥락 유지
    새 탭 or 새로고침 = 새 thread_id = 독립된 대화
"""

import gradio as gr
from src.rag.agent import ResumeAgent

agent = ResumeAgent(db_dir="data/vector_db")


def chat(message: str, history: list, request: gr.Request) -> str:
    # 브라우저 세션마다 고유한 thread_id 사용 → 대화 맥락 유지
    thread_id = request.session_hash
    return agent.ask(message, thread_id=thread_id)


demo = gr.ChatInterface(
    fn=chat,
    title="아이코어 챗봇",
    description="강사 정보를 검색하고 추천받을 수 있습니다.",
    examples=[
        "Python 강의 가능한 강사 추천해줘",
        "데이터분석이랑 AI 둘 다 가능한 강사 있어?",
        "현재 보유한 강사 리스트 뽑아줘",
    ],
)

if __name__ == "__main__":
    demo.launch()
