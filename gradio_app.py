import re
from pathlib import Path

template_path = Path(gr.__file__).parent / "templates" / "frontend" / "index.html"
if template_path.exists():
    html_content = template_path.read_text(encoding="utf-8")
    
    # 카카오톡 로봇이 읽을 수 있도록 순수 HTML의 사진과 제목을 직접 교체 (정규식 사용)
    html_content = re.sub(
        r'<meta\s+property="og:image"[^>]*>', 
        '<meta property="og:image" content="https://aicorechatbot.site/aicore_logo.png" />', 
        html_content
    )
    html_content = re.sub(
        r'<meta\s+property="og:title"[^>]*>', 
        '<meta property="og:title" content="아이코어 통합 챗봇" />', 
        html_content
    )
    html_content = re.sub(
        r'<title>.*?</title>', 
        '<title>아이코어 통합 챗봇</title>', 
        html_content
    )
    
    # 덮어쓰기 저장
    template_path.write_text(html_content, encoding="utf-8")

"""
아이코어 통합 UI (Gradio)
실행: python gradio_app.py

탭 구성:
    [챗봇]      강사 검색 / 커리큘럼 생성 (RAG Agent)
    [줌 출석]   줌 로그 CSV 업로드 → 학생별 총 참석 시간 CSV 다운로드

세션 관리:
    gr.Request.session_hash → 브라우저 탭마다 고유한 ID 자동 부여
    같은 탭 = 같은 thread_id = 대화 맥락 유지
    새 탭 or 새로고침 = 새 thread_id = 독립된 대화
"""

import os
import tempfile

import gradio as gr

from src.rag.agent import ResumeAgent
from src.zoom.zoom_log_processor import process_zoom_log

agent = ResumeAgent(db_dir="data/vector_db")


# ── 챗봇 탭 ──────────────────────────────────────────────────────────────────

def chat(message: str, history: list, request: gr.Request) -> str:
    thread_id = request.session_hash
    return agent.ask(message, thread_id=thread_id)


chatbot_tab = gr.ChatInterface(
    fn=chat,
    title="아이코어 챗봇",
    description="강사 정보 검색 및 커리큘럼 생성/추천을 포함한 아이코어 사내 데이터를 기반으로 업무를 도와드립니다.",
    examples=[
        "Python이랑 데이터분석 둘 다 가능한 강사 추천해줘",
        "AI 관련 강의 경험 있는 강사 알려줘",
        "현재 보유한 강사 리스트 뽑아줘",
        "비전공 대학생 대상 Python 데이터분석 160시간 커리큘럼 만들어줘",
        "최신 클라우드 기술 동향을 반영한 대학생 전공자 대상 DevOps 80시간 커리큘럼 추천해줘",
        "LLM 서비스 개발 기업 현직자 대상 커리큘럼 만들어줘"
    ],
)


# ── 줌 출석 탭 ────────────────────────────────────────────────────────────────

def process_zoom_csv(file_obj):
    """
    업로드된 줌 로그 CSV를 처리하여 학생별 총 참석 시간 표와 다운로드 파일 반환.
    """
    if file_obj is None:
        return None, None, "CSV 파일을 업로드해주세요."

    with open(file_obj.name, "rb") as f:
        file_bytes = f.read()

    try:
        result_df, csv_bytes = process_zoom_log(file_bytes)
    except ValueError as e:
        return None, None, f"오류: {e}"

    # 임시 파일로 저장 (Gradio 다운로드용)
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix="_출석집계.csv", mode="wb"
    )
    tmp.write(csv_bytes)
    tmp.close()

    summary = f"총 {len(result_df)}명 집계 완료"
    return result_df, tmp.name, summary


with gr.Blocks() as zoom_tab:
    gr.Markdown("## 줌 출석 집계")
    gr.Markdown(
        "줌 로그 CSV 파일을 업로드하면 학생별 총 참석 시간을 자동으로 집계합니다.\n\n"
        "**출력 항목:** 주제 · 수업 시작/종료 시간 · 학생이름 · 총 시간(분) · 첫 입장시간 · 최종 퇴실시간\n\n"
        "---\n\n"
        "**⚠️ 주의사항**\n\n"
        "- 반드시 **줌(Zoom)에서 내보내기한 CSV 파일**을 업로드해주세요. `.xlsx` 등 다른 형식은 지원하지 않습니다.\n"
        "- 같은 참석자가 다른 이름으로 찍힌 경우 자동 병합됩니다.\n"
        "  (예: `당감초 안한비 (iPhone)` + `당감초 안한비 (안 한비)` → `당감초 안한비`, `환서초등학교_박정희 (Samsung SM-S911N)` + `환서초등학교_박정희` → `환서초등학교_박정희`)\n"
        "- **첫 입장시간 / 최종 퇴실시간**은 개별 접속 기록이 포함된 파일에서만 표시됩니다.\n"
        "  참석자별 입장, 퇴장시간이 없는 경우는 해당 항목이 `-`로 표시됩니다.\n"
    )

    with gr.Row():
        file_input = gr.File(label="줌 로그 CSV 업로드", file_types=[".csv"])
        run_btn = gr.Button("집계 시작", variant="primary")

    status_text = gr.Textbox(label="상태", interactive=False)
    result_table = gr.Dataframe(label="학생별 총 참석 시간", interactive=False)
    download_file = gr.File(label="CSV 다운로드")

    run_btn.click(
        fn=process_zoom_csv,
        inputs=[file_input],
        outputs=[result_table, download_file, status_text],
    )


# ── 앱 실행 ───────────────────────────────────────────────────────────────────

HTML_HEAD = """
<meta property="og:title" content="아이코어 챗봇">
<meta property="og:description" content="사내 데이터를 기반으로 업무를 도와드립니다.">
<meta property="og:image" content="https://aicorechatbot.site/aicore_logo.png"> 
"""

with gr.Blocks(head=HTML_HEAD) as demo:
    with gr.Tab("챗봇"):
        chatbot_tab.render()
    with gr.Tab("줌 출석 집계"):
        zoom_tab.render()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
