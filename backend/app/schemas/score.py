from pydantic import BaseModel


class ScoreCreateRequest(BaseModel):
    value: bool
    description: str
