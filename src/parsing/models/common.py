from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """벡터 DB에 저장할 청크 단위"""
    content: str = Field(description="임베딩할 텍스트 (컨텍스트 prefix 포함)")
    metadata: dict = Field(description="필터링에 사용할 메타데이터")
