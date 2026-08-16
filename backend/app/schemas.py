from pydantic import BaseModel, Field


class CorrectionRequest(BaseModel):
    text: str = Field(min_length=1)


class ChangeItem(BaseModel):
    before: str
    after: str
    reason: str


class VocabularySuggestion(BaseModel):
    word: str
    suggestion: str
    reason: str


class CorrectionPayload(BaseModel):
    original_text: str
    corrected_text: str
    natural_alternative: str
    explanation: str
    changes: list[ChangeItem] = []
    vocabulary_suggestions: list[VocabularySuggestion] = []


class CorrectionResponse(CorrectionPayload):
    id: int
    created_at: str


class HealthResponse(BaseModel):
    status: str
    model_id: str
    llm_ready: bool
