from pydantic import BaseModel


class ScoreCreateRequest(BaseModel):
    summary_id: int
    value: bool
    description: str


class ScoreCreateResponse(BaseModel):
    id: int
    summary_id: int
    value: bool
    description: str
