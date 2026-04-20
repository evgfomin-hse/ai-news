from pydantic import BaseModel, Field


class UserMeOut(BaseModel):
    id: str
    username: str
    email: str
    avatarUrl: str | None = None


class UserMePatch(BaseModel):
    name: str | None = None
    picture: str | None = None


class GoogleLoginBody(BaseModel):
    token: str = Field(..., min_length=1, description="Google ID token (JWT) from credential")


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    avatarUrl: str | None = None


class GoogleLoginJson(BaseModel):
    """Returned in the response body; session JWT is only in an HttpOnly cookie."""

    user: UserOut
