from enum import Enum
from typing import Any

from pydantic import BaseModel


class LLMModel(Enum):
    OPENAI = "openai"
    AZURE = "azure"
    ANTHROPIC = "anthropic"
    GROQ = "groq"


class TextConversionResponse(BaseModel):
    # The generated code to be executed
    code: str
    # The output of the code execution
    content: Any
