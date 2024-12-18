from typing import Any, Dict, List, Literal, Optional

from groq import Groq
from groq.types.chat import ChatCompletion
from openai.types.chat.completion_create_params import Function


class GroqModel:
    def __init__(self, api_key: str, model: Optional[str] = "llama-3.1-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model = model

    def call_function_call(
        self, messages: List[Dict[str, Any]], functions: List[Function]
    ) -> ChatCompletion:
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=functions,
            tool_choice={
                "type": "function",
                "function": {
                    "name": functions[0]["function"]["name"],
                },
            },
        )

    def get_generate_sql_params(self) -> Function:
        return {
            "type": "function",
            "function": {
                "name": "generate_sql",
                "description": "Generate SQL query based on user prompt",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "The SQL query generated based on the prompt",
                        }
                    },
                    "required": ["sql"],
                },
            },
        }

    def get_generate_code_params(
        self, code_type: Literal["markdown", "html"]
    ) -> Function:
        return {
            "type": "function",
            "function": {
                "name": f"generate_{code_type}",
                "description": f"Generate {code_type} based on user prompt",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": f"The {code_type} code generated based on the prompt",
                        }
                    },
                    "required": ["code"],
                },
            },
        }

    def get_plotly_code_params(self) -> Function:
        return {
            "type": "function",
            "function": {
                "name": "generate_python_code",
                "description": "Generate python code using plotly for visualization based on user prompt",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The python code using plotly generated based on the prompt",
                        }
                    },
                    "required": ["code"],
                },
            },
        }

    def get_matplotlib_code_params(self) -> Function:
        return {
            "type": "function",
            "function": {
                "name": "generate_python_code",
                "description": "Generate python code using matplotlib for visualization based on user prompt",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The python code using matplotlib generated based on the prompt",
                        }
                    },
                    "required": ["code"],
                },
            },
        }
