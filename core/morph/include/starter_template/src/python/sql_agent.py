import json
import os
from typing import Generator

from morph_lib.database import execute_sql
from morph_lib.stream import stream_chat
from morph_lib.types import MorphChatStreamChunk
from openai import OpenAI

import morph
from morph import MorphGlobalContext


@morph.func(name="sql_agent")
def sql_agent(
    context: MorphGlobalContext,
) -> Generator[MorphChatStreamChunk, None, None]:
    if os.getenv("OPENAI_API_KEY") is None:
        yield stream_chat("Please set your OPENAI_API_KEY in .env file.")
        return
    # context.user_info comes from user's authentication info.
    if context.user_info is None or "Admin" not in context.user_info["roles"]:
        yield stream_chat("You are not authorized to use this feature.")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    prompt = context.vars["prompt"]
    messages = [
        {
            "role": "system",
            "content": """Please execute SQL queries on a table named ./data/Traffic_Orders_Demo_Data.csv in DuckDB with the following schema:
Date: text - date
Source: text - traffic source (Coupon, Google Organic など)
Traffic: int - traffic count
Orders: int - order count

This table contains traffic and order data for the marketing campaigns.

As a source, you have the following data:
- Coupon
- Google Organic
- Google Paid
- TikTok Ads
- Meta Ads
- Referral
""",
        }
    ]
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        functions=[
            {
                "name": "generate_sql",
                "description": "Generate SQL queries based on user prompt",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "The SQL query generated based on the prompt",
                        },
                    },
                    "required": ["sql"],
                },
            }
        ],
    )

    response_json = json.loads(response.choices[0].message.function_call.arguments)
    sql = response_json["sql"]
    yield stream_chat(
        f"""
## SQL Query
```sql
{sql}
```
"""
    )
    data = execute_sql(sql, "DUCKDB")
    data_md = data.to_markdown(index=False)
    yield stream_chat(
        f"""
{data_md}
"""
    )
    messages.extend(
        [
            {
                "role": "system",
                "content": f"""Please answer in markdown format.
You can use the following data:
{data_md}
""",
            },
            {"role": "user", "content": prompt},
        ]
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        stream=True,
    )

    for chunk in response:
        yield stream_chat(chunk.choices[0].delta.content)
