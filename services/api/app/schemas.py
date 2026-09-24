from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Agent = Literal['auto', 'coding', 'document', 'search', 'research']


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=12000)
    agent: Agent = 'auto'
    document_id: str | None = Field(default=None, max_length=100)

    @field_validator('message')
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Enter a task before sending.')
        return value.strip()


class Activity(BaseModel):
    step: str
    status: Literal['completed'] = 'completed'
    detail: str
    duration_ms: int


class Citation(BaseModel):
    id: str
    title: str
    url: str | None = None
    page: int | None = None
    document_id: str | None = None
    excerpt: str | None = None


class Usage(BaseModel):
    """Model usage metadata for metering; absent for non-model providers."""
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int
    stop_reason: str | None = None
    truncated: bool = False
    attempts: int = 1


class ChatResponse(BaseModel):
    request_id: str
    agent: str
    answer: str
    provider: Literal['demo', 'bedrock', 'extractive', 'tavily']
    activity: list[Activity]
    citations: list[Citation] = Field(default_factory=list)
    usage: Usage | None = None
