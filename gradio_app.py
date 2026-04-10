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
    description="강사 정보 검색 및 커리큘럼 생성/추천을 도와드립니다.",
    examples=[
        "Python이랑 데이터분석 둘 다 가능한 강사 추천해줘",
        "AI 관련 강의 경험 있는 강사 알려줘",
        "현재 보유한 강사 리스트 뽑아줘",
        "비전공 대학생 대상 Python 데이터분석 160시간 커리큘럼 만들어줘",
        "AWS 클라우드 초급 과정 80시간 커리큘럼 추천해줘",
        "LLM 서비스 개발 기업 현직자 대상 커리큘럼 만들어줘",
    ],
)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
