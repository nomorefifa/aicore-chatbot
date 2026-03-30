"""
벡터 DB 검색 테스트
실행: python test/search_test.py
"""
import sys
sys.path.insert(0, ".")

from src.embedding import EmbeddingStore

store = EmbeddingStore(collection_name="instructor_resumes")
print(f"DB 총 청크 수: {store.count()}\n")

# ── 테스트 쿼리 목록 ──────────────────────────────────
queries = [
    "Python 강의 경험",
    "데이터분석 전문가",
    "AI 머신러닝 강사",
    "중소기업 컨설팅",
]

for query in queries:
    print(f"{'='*55}")
    print(f"쿼리: {query}")
    print(f"{'='*55}")

    results = store.search(query, n_results=3)
    for i, r in enumerate(results, 1):
        name = r["metadata"]["instructor_name"]
        section = r["metadata"]["section"]
        similarity = 1 - r["distance"]
        content = r["content"][:100]
        print(f"  [{i}] {name} | {section} | 유사도: {similarity:.3f}")
        print(f"      {content}")
    print()

# ── 섹션 필터 테스트 ──────────────────────────────────
print(f"{'='*55}")
print("쿼리: Python (강의이력 섹션만 필터)")
print(f"{'='*55}")
results = store.search("Python", n_results=5, filter={"section": "강의이력"})
for i, r in enumerate(results, 1):
    name = r["metadata"]["instructor_name"]
    similarity = 1 - r["distance"]
    content = r["content"][:100]
    print(f"  [{i}] {name} | 유사도: {similarity:.3f}")
    print(f"      {content}")
