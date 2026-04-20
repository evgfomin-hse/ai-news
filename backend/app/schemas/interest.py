from pydantic import BaseModel, Field


class InterestMeOut(BaseModel):
    interestId: int | None = None
    interests: str = ""


class InterestMePatch(BaseModel):
    interests: str = Field(
        default="",
        max_length=50_000,
        description="Free-text interests for this user.",
    )
