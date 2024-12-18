from typing import Any, Dict, List, Literal, Optional

from openai import OpenAI
from openai.types.chat import ChatCompletion
from openai.types.chat.completion_create_params import Function


class OpenAIModel:
    def __init__(self, api_key: str, model: Optional[str] = "gpt-4o"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def call_function_call(
        self, messages: List[Dict[str, Any]], functions: List[Function]
    ) -> ChatCompletion:
        return self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            functions=functions,
        )

    def get_generate_sql_params(self) -> Function:
        return {
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
        }

    def get_generate_code_params(
        self, code_type: Literal["markdown", "html"]
    ) -> Function:
        return {
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
        }

    def get_plotly_code_params(self) -> Function:
        return {
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
        }

    def get_matplotlib_code_params(self) -> Function:
        return {
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
        }
