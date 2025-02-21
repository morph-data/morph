from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class HtmlResponse(BaseModel):
    value: str

    def __init__(self, value: str):
        super().__init__(value=value)


class MarkdownResponse(BaseModel):
    value: str

    def __init__(self, value: str):
        super().__init__(value=value)


class ImageResponse(BaseModel):
    value: str

    def __init__(self, value: str):
        super().__init__(value=value)


class MorphChatStreamChunk(BaseModel):
    text: Optional[str] = Field(default="")
    content: Optional[str] = Field(default="")

    @staticmethod
    def is_chat_stream_chunk_json(data: Dict[str, Any]) -> bool:
        return (
            isinstance(data, dict)
            and "data" in data
            and isinstance(data["data"], list)
            and all("text" in item and "content" in item for item in data["data"])
        )
