from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    repository_id: str = Field(default="demo", min_length=1, max_length=512)
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=5, ge=1, le=20)

class AnalyzeRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=100)
    repo: str = Field(min_length=1, max_length=100)
    branch: str = Field(min_length=1, max_length=255)
