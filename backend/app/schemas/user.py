from pydantic import BaseModel, Field


class UserProfileOut(BaseModel):
    id: str
    username: str
    email: str
    avatarUrl: str | None = None


class LoginBody(BaseModel):
    token: str = Field(..., min_length=1, description="OAuth ID token (JWT) from credential")


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    avatarUrl: str | None = None


class LoginJson(BaseModel):
    """Returned in the response body; session JWT is only in an HttpOnly cookie."""

    user: UserOut
