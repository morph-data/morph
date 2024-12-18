import json
from typing import Any, Dict, List, Literal, Optional, cast

import pandas as pd
from morph_lib.ai.anthropic.model import AnthropicModel
from morph_lib.ai.azure.model import AzureOpenAIModel
from morph_lib.ai.common.prompt import (
    get_generate_python_code_system_prompt,
    get_generate_visualization_code_base_prompt,
    get_text_to_sql_prompt,
)
from morph_lib.ai.common.types import LLMModel, TextConversionResponse
from morph_lib.ai.groq.model import GroqModel
from morph_lib.ai.openai.model import OpenAIModel


def text_to_sql_impl(
    llm_model: LLMModel,
    api_key: str,
    prompt: str,
    table_names: List[str],
    connection: Optional[str] = None,
    schema_name: Optional[str] = None,
    opts: Dict[str, Any] = {},
) -> TextConversionResponse:
    messages = get_text_to_sql_prompt(prompt, connection, table_names, schema_name)

    if llm_model == LLMModel.OPENAI:
        openai_model = OpenAIModel(api_key=api_key, model=opts.get("model"))
        response = openai_model.call_function_call(
            messages, [openai_model.get_generate_sql_params()]
        )
        sql = cast(
            str, json.loads(response.choices[0].message.function_call.arguments)["sql"]
        )
        return TextConversionResponse(code=sql, content=sql)
    elif llm_model == LLMModel.AZURE:
        azure_model = AzureOpenAIModel(
            api_key=api_key,
            azure_endpoint=opts.get("azure_endpoint", ""),
            deployment_name=opts.get("deployment_name"),
            api_version=opts.get("api_version"),
        )
        response = azure_model.call_function_call(
            messages, [azure_model.get_generate_sql_params()]
        )
        sql = cast(
            str, json.loads(response.choices[0].message.function_call.arguments)["sql"]
        )
        return TextConversionResponse(code=sql, content=sql)
    elif llm_model == LLMModel.GROQ:
        groq_model = GroqModel(api_key=api_key, model=opts.get("model"))
        response = groq_model.call_function_call(
            messages, [groq_model.get_generate_sql_params()]
        )
        sql = cast(
            str,
            json.loads(response.choices[0].message.tool_calls[0].function.arguments)[
                "sql"
            ],
        )
        return TextConversionResponse(code=sql, content=sql)
    elif llm_model == LLMModel.ANTHROPIC:
        anthropic_model = AnthropicModel(
            api_key=api_key, model=opts.get("model"), max_tokens=opts.get("max_tokens")
        )
        response = anthropic_model.call_function_call(
            messages, [anthropic_model.get_generate_sql_params()]
        )
        sql = cast(
            str,
            next(
                (
                    content["input"]["sql"]
                    for content in response.model_dump()["content"]
                    if "input" in content and "sql" in content["input"]
                ),
                "",
            ),
        )
        return TextConversionResponse(code=sql, content=sql)
    else:
        raise ValueError(f"Unsupported LLM model: {llm_model}")


def text_to_code_impl(
    code_type: Literal["markdown", "html"],
    llm_model: LLMModel,
    api_key: str,
    prompt: str,
    opts: Dict[str, Any] = {},
) -> TextConversionResponse:
    messages = [
        {
            "role": "system",
            "content": f"""You are a great data analyst using python. You can generate {code_type} code based on user prompt and you can use given python libraries.
            """,
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]

    if llm_model == LLMModel.OPENAI:
        openai_model = OpenAIModel(api_key=api_key, model=opts.get("model"))
        response = openai_model.call_function_call(
            messages, [openai_model.get_generate_code_params(code_type)]
        )
        code = cast(
            str, json.loads(response.choices[0].message.function_call.arguments)["code"]
        )
        return TextConversionResponse(code=code, content=code)
    elif llm_model == LLMModel.AZURE:
        azure_model = AzureOpenAIModel(
            api_key=api_key,
            azure_endpoint=opts.get("azure_endpoint", ""),
            deployment_name=opts.get("deployment_name"),
            api_version=opts.get("api_version"),
        )
        response = azure_model.call_function_call(
            messages, [azure_model.get_generate_code_params(code_type)]
        )
        code = cast(
            str, json.loads(response.choices[0].message.function_call.arguments)["code"]
        )
        return TextConversionResponse(code=code, content=code)
    elif llm_model == LLMModel.GROQ:
        groq_model = GroqModel(api_key=api_key, model=opts.get("model"))
        response = groq_model.call_function_call(
            messages, [groq_model.get_generate_code_params(code_type)]
        )
        code = cast(
            str,
            json.loads(response.choices[0].message.tool_calls[0].function.arguments)[
                "code"
            ],
        )
        return TextConversionResponse(code=code, content=code)
    elif llm_model == LLMModel.ANTHROPIC:
        anthropic_model = AnthropicModel(
            api_key=api_key, model=opts.get("model"), max_tokens=opts.get("max_tokens")
        )
        response = anthropic_model.call_function_call(
            messages, [anthropic_model.get_generate_code_params(code_type)]
        )
        code = cast(
            str,
            next(
                (
                    content["input"]["code"]
                    for content in response.model_dump()["content"]
                    if "input" in content and "code" in content["input"]
                ),
                "",
            ),
        )
        return TextConversionResponse(code=code, content=code)
    else:
        raise ValueError(f"Unsupported LLM model: {llm_model}")


def _text_to_visualization_impl(
    lib: Literal["plotly", "matplotlib"],
    llm_model: LLMModel,
    api_key: str,
    prompt: str,
    df: pd.DataFrame,
    opts: Dict[str, Any] = {},
) -> TextConversionResponse:
    messages = [
        {"role": "system", "content": get_generate_python_code_system_prompt()},
        {
            "role": "system",
            "content": get_generate_visualization_code_base_prompt(lib, df),
        },
        {
            "role": "user",
            "content": prompt,
        },
    ]
    code = ""

    if llm_model == LLMModel.OPENAI:
        openai_model = OpenAIModel(api_key=api_key, model=opts.get("model"))
        functions = (
            openai_model.get_plotly_code_params()
            if lib == "plotly"
            else openai_model.get_matplotlib_code_params()
        )
        response = openai_model.call_function_call(messages, [functions])
        code = json.loads(response.choices[0].message.function_call.arguments)["code"]
    elif llm_model == LLMModel.AZURE:
        azure_model = AzureOpenAIModel(
            api_key=api_key,
            azure_endpoint=opts.get("azure_endpoint", ""),
            deployment_name=opts.get("deployment_name"),
            api_version=opts.get("api_version"),
        )
        functions = (
            azure_model.get_plotly_code_params()
            if lib == "plotly"
            else azure_model.get_matplotlib_code_params()
        )
        response = azure_model.call_function_call(messages, [functions])
        code = json.loads(response.choices[0].message.function_call.arguments)["code"]
    elif llm_model == LLMModel.GROQ:
        groq_model = GroqModel(api_key=api_key, model=opts.get("model"))
        functions = (
            groq_model.get_plotly_code_params()
            if lib == "plotly"
            else groq_model.get_matplotlib_code_params()
        )
        response = groq_model.call_function_call(messages, [functions])
        code = json.loads(response.choices[0].message.tool_calls[0].function.arguments)[
            "code"
        ]
    elif llm_model == LLMModel.ANTHROPIC:
        anthropic_model = AnthropicModel(
            api_key=api_key, model=opts.get("model"), max_tokens=opts.get("max_tokens")
        )
        functions = (
            anthropic_model.get_plotly_code_params()
            if lib == "plotly"
            else anthropic_model.get_matplotlib_code_params()
        )
        response = anthropic_model.call_function_call(messages, [functions])
        code = next(
            content["input"]["code"]
            for content in response.model_dump()["content"]
            if "input" in content and "code" in content["input"]
        )
    else:
        raise ValueError(f"Unsupported LLM model: {llm_model}")

    code_ = compile(code, "<string>", "exec")
    namespace: Dict[str, Any] = {}
    exec(code_, namespace)
    func = namespace["main"]

    output = func(df)

    return TextConversionResponse(code=code, content=output)


def text_to_plotly_impl(
    llm_model: LLMModel,
    api_key: str,
    prompt: str,
    df: pd.DataFrame,
    opts: Dict[str, Any] = {},
) -> TextConversionResponse:
    return _text_to_visualization_impl("plotly", llm_model, api_key, prompt, df, opts)


def text_to_matplotlib_impl(
    llm_model: LLMModel,
    api_key: str,
    prompt: str,
    df: pd.DataFrame,
    opts: Dict[str, Any] = {},
) -> TextConversionResponse:
    return _text_to_visualization_impl(
        "matplotlib", llm_model, api_key, prompt, df, opts
    )
