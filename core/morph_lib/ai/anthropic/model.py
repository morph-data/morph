from typing import Any, Dict, List, Literal, Optional, Tuple

from anthropic import Anthropic
from anthropic.types import Message
from openai.types.chat.completion_create_params import Function


class AnthropicModel:
    def __init__(
        self,
        api_key: str,
        model: Optional[str] = "claude-3-5-haiku-latest",
        max_tokens: Optional[int] = 1024,
    ):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    def _get_system_message(
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        system = ""
        messages_ = []
        for message in messages:
            if message["role"] == "system":
                system += message["content"]
            else:
                messages_.append(message)
        return system, messages_

    def call_function_call(
        self, messages: List[Dict[str, Any]], functions: List[Function]
    ) -> Message:
        system_, messages_ = self._get_system_message(messages)

        return self.client.messages.create(
            system=system_,
            model=self.model,
            messages=messages_,
            max_tokens=self.max_tokens,
            tools=functions,
        )

    def get_generate_sql_params(self) -> Function:
        return {
            "name": "generate_sql",
            "description": "Generate SQL query based on user prompt",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL query generated based on the prompt",
                    }
                },
                "required": ["sql"],
            },
        }

    def get_generate_code_params(
        self, code_type: Literal["markdown", "html"]
    ) -> Function:
        return {
            "name": f"generate_{code_type}",
            "description": f"Generate {code_type} based on user prompt",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": f"The {code_type} code generated based on the prompt",
                    }
                },
                "required": ["code"],
            },
        }

    def get_plotly_code_params(self) -> Function:
        return {
            "name": "generate_python_code",
            "description": "Generate python code using plotly for visualization based on user prompt",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The python code using plotly generated based on the prompt",
                    }
                },
                "required": ["code"],
            },
        }

    def get_matplotlib_code_params(self) -> Function:
        return {
            "name": "generate_python_code",
            "description": "Generate python code using matplotlib for visualization based on user prompt",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The python code using matplotlib generated based on the prompt",
                    }
                },
                "required": ["code"],
            },
        }
