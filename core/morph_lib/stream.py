from typing import Optional

from morph_lib.types import MorphChatStreamChunk


def create_chunk(
    text: Optional[str] = None, content: Optional[str] = None
) -> MorphChatStreamChunk:
    """
    Create a MorphChatStreamChunk object with the given text and content.
    @param text: The text of the chunk.
    @param content: The additional content of the chunk. ex.) html, markdown, etc.
    """
    return MorphChatStreamChunk(
        text=text,
        content=content,
    )


def stream_chat(text: Optional[str] = None) -> MorphChatStreamChunk:
    """
    Create a MorphChatStreamChunk object with the given text and content.
    @param text: The text of the chunk.
    @param content: The additional content of the chunk. ex.) html, markdown, etc.
    """
    return MorphChatStreamChunk(text=text, content=None)
