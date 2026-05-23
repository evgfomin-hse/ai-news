from pydantic import BaseModel, Field


class TransportOut(BaseModel):
    transportId: int | None = None
    telegramConfigured: bool = False
    """Telegram chat id for outbound messages; null until the user saves it."""
    telegramChatId: str | None = None


class TransportPatch(BaseModel):
    telegramBotToken: str | None = Field(
        default=None,
        description=(
            "Set or replace token; empty string removes token (and chat id). Omit = no change."
        ),
    )
    telegramChatId: str | None = Field(
        default=None,
        description="Numeric chat id for sendMessage; empty string clears. Omit = no change.",
    )


class TelegramTestOut(BaseModel):
    ok: bool = True
    botUsername: str | None = None
    botId: int | None = None


class SendMessageBody(BaseModel):
    text: str = Field(
        default="Test message from HSE repos.",
        max_length=4096,
    )


class SendMessageOut(BaseModel):
    ok: bool = True
    telegramMessageId: int | None = None


class CaptureHelloOut(BaseModel):
    linked: bool
    chatId: str | None = None
    hint: str | None = None
