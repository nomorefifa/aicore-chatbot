"""
강사 이력서 RAG 체인 (LCEL 기반)

LCEL(LangChain Expression Language): | 연산자로 체인을 연결하는 방식
langchain 1.x 이상에서 표준 방식

흐름:
    사용자 질문
        → Retriever (벡터DB 검색) ─────────────────┐
        → format_docs (청크 텍스트로 변환)          │
        → Prompt (질문 + context 조합)              │ context 문서도 함께 반환
        → LLM (Gemini)                             │
        → 답변                                     │
"""

import logging
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from langchain_google_genai import ChatGoogleGenerativeAI

from src.embedding.embedder import EmbeddingStore

load_dotenv()
logger = logging.getLogger(__name__)

PROMPT = ChatPromptTemplate.from_template("""
당신은 강사 매칭 전문가입니다.
아래 강사 정보를 바탕으로 질문에 답변하세요.
강사 정보에 없는 내용은 "확인되지 않습니다"라고 답하세요.

=== 강사 정보 ===
{context}

=== 질문 ===
{input}
""")


def _format_docs(docs) -> str:
    """검색된 Document 목록을 하나의 텍스트로 합침"""
    return "\n\n".join(doc.page_content for doc in docs)


class ResumeRAGChain:
    """
    강사 이력서 RAG 체인.

    사용 예시:
        rag = ResumeRAGChain()
        result = rag.ask("Python 강의 가능한 강사 추천해줘")
        print(result['answer'])
        print(result['context'])  # 검색에 사용된 청크 목록
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        collection_name: str = "instructor_resumes",
        db_dir: str = "data/vector_db",
        k: int = 5,
        search_filter: dict | None = None,
    ):
        llm = ChatGoogleGenerativeAI(model=model, temperature=0)

        store = EmbeddingStore(collection_name=collection_name, db_dir=db_dir)
        retriever = store.db.as_retriever(
            search_kwargs={
                "k": k,
                **({"filter": search_filter} if search_filter else {})
            }
        )

        # LCEL 체인 조립
        #
        # RunnableParallel: 입력을 두 갈래로 동시에 처리
        #   - "context": retriever로 청크 검색 → _format_docs로 텍스트 변환
        #   - "input": 질문 그대로 통과
        #
        # | PROMPT: context + input을 프롬프트에 채움
        # | llm: Gemini 호출
        # | StrOutputParser: 응답에서 텍스트만 추출
        answer_chain = (
            RunnablePassthrough.assign(context=lambda x: _format_docs(x["context"]))
            | PROMPT
            | llm
            | StrOutputParser()
        )

        # context 문서 + 답변을 함께 반환하는 체인
        self.chain = RunnableParallel(
            context=retriever,
            input=RunnablePassthrough()
        ).assign(answer=answer_chain)

        logger.info(f"RAG 체인 준비 완료 | 모델: {model} | 검색 청크 수: {k}")

    def ask(self, question: str) -> dict:
        """
        Returns:
            {
                "answer": "LLM 답변",
                "context": [검색된 Document 목록],
                "input": "원본 질문"
            }
        """
        logger.info(f"질문: {question}")
        result = self.chain.invoke(question)
        logger.info("답변 생성 완료")
        return result
