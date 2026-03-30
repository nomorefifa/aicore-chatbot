import sys
sys.path.insert(0, '.')

from src.parsing import run_pdf_pipeline
from src.embedding import EmbeddingStore

chunks = run_pdf_pipeline(
    raw_dir='data/raw/raw_pdf',
    parsed_dir='data/parsed'
)

store = EmbeddingStore(
    collection_name='instructor_resumes',
    db_dir='data/vector_db'
)
store.add(chunks)
print(f"총 저장 청크 수: {store.count()}")