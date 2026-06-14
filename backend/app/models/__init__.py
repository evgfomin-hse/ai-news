"""SQLAlchemy ORM models (import this package so all tables register on `Base.metadata`)."""

from app.models.base import Base
from app.models.interest import Interest
from app.models.news_article import NewsArticle
from app.models.score import Score
from app.models.summary import Summary
from app.models.transport import Transport
from app.models.user import User

__all__ = ["Base", "Interest", "NewsArticle", "Score", "Summary", "Transport", "User"]
