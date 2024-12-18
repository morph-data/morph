from typing import List, Optional

import pandas as pd
from morph_lib.ai.common.code_generation import (
    text_to_code_impl,
    text_to_matplotlib_impl,
    text_to_plotly_impl,
    text_to_sql_impl,
)
from morph_lib.ai.common.types import LLMModel, TextConversionResponse


def text_to_sql(
    prompt: str,
    api_key: str,
    table_names: List[str],
    model: Optional[str] = "gpt-4o",
    connection: Optional[str] = None,
    schema_name: Optional[str] = None,
) -> TextConversionResponse:
    """
    Generate SQL query based on user prompt.
    @param prompt: The user question prompt.
    @param api_key: The OpenAI API key. Recommended to use the environment variable.
    @param table_names: The table names to give structures to ai.
    @param model: The OpenAI model to use. Default is "gpt-4o".
    @param connection: The connection to retrieve tables and fields. Default connection is Morph built-in database.
    @param schema_name: The schema name to give structures to ai.
    """
    return text_to_sql_impl(
        llm_model=LLMModel.OPENAI,
        api_key=api_key,
        prompt=prompt,
        connection=connection,
        table_names=table_names,
        schema_name=schema_name,
        opts={"model": model},
    )


def text_to_html(
    prompt: str,
    api_key: str,
    model: Optional[str] = "gpt-4o",
) -> TextConversionResponse:
    """
    Generate HTML code based on user prompt.
    @param prompt: The user question prompt.
    @param api_key: The OpenAI API key. Recommended to use the environment variable.
    @param table_names: The table names to give structures to ai.
    @param model: The OpenAI model to use. Default is "gpt-4o".
    @param connection: The connection to retrieve tables and fields. Default connection is Morph built-in database.
    @param schema_name: The schema name to give structures to ai.
    """
    return text_to_code_impl(
        code_type="html",
        llm_model=LLMModel.OPENAI,
        api_key=api_key,
        prompt=prompt,
        opts={"model": model},
    )


def text_to_markdown(
    prompt: str,
    api_key: str,
    model: Optional[str] = "gpt-4o",
) -> TextConversionResponse:
    """
    Generate markdown based on user prompt.
    @param prompt: The user question prompt.
    @param api_key: The OpenAI API key. Recommended to use the environment variable.
    @param table_names: The table names to give structures to ai.
    @param model: The OpenAI model to use. Default is "gpt-4o".
    @param connection: The connection to retrieve tables and fields. Default connection is Morph built-in database.
    @param schema_name: The schema name to give structures to ai.
    """
    return text_to_code_impl(
        code_type="markdown",
        llm_model=LLMModel.OPENAI,
        api_key=api_key,
        prompt=prompt,
        opts={"model": model},
    )


def text_to_plotly(
    prompt: str,
    api_key: str,
    df: pd.DataFrame,
    model: Optional[str] = "gpt-4o",
) -> TextConversionResponse:
    """
    Generate Plotly code based on user prompt.
    @param prompt: The user question prompt.
    @param api_key: The OpenAI API key. Recommended to use the environment variable.
    @param df: The DataFrame to visualize.
    @param model: The OpenAI model to use. Default is "gpt-4o".
    """
    return text_to_plotly_impl(
        llm_model=LLMModel.OPENAI,
        api_key=api_key,
        prompt=prompt,
        df=df,
        opts={"model": model},
    )


def text_to_matplotlib(
    prompt: str,
    api_key: str,
    df: pd.DataFrame,
    model: Optional[str] = "gpt-4o",
) -> TextConversionResponse:
    """
    Generate Matplotlib code based on user prompt.
    @param prompt: The user question prompt.
    @param api_key: The OpenAI API key. Recommended to use the environment variable.
    @param df: The DataFrame to visualize.
    @param model: The OpenAI model to use. Default is "gpt-4o".
    """
    return text_to_matplotlib_impl(
        llm_model=LLMModel.OPENAI,
        api_key=api_key,
        prompt=prompt,
        df=df,
        opts={"model": model},
    )
