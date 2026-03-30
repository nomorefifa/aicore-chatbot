from dotenv import load_dotenv
import os
load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
try:
    response = llm.invoke("안녕하세요")
    print(f"LLM 응답: {response.content}")
except Exception as e:
    print(f"LLM 에러 발생: {e}")

# 2. Embedding 테스트
embeddings = GoogleGenerativeAIEmbeddings(model="gemini-embedding-004")
try:
    result = embeddings.embed_query("테스트")
    print(f"임베딩 차원: {len(result)}")  # 768
except Exception as e:
    print(f"Embedding 에러 발생: {e}")
