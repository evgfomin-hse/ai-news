from pydantic import BaseModel, ConfigDict, Field


class ScoreUpsertRequest(BaseModel):
    summary_id: int = Field(..., ge=1, description="Target summary row id.")
    value: bool = Field(..., description="True = thumbs-up, False = thumbs-down.")
    description: str | None = Field(default=None, max_length=4096)


class ScoreOut(BaseModel):
    """Response shape; maps ORM `score` column onto the public `value` field."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    summary_id: int
    value: bool | None = Field(default=None, validation_alias="score")
    description: str | None = None
