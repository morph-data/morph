from typing import Any, Dict, List, Literal, Optional

import pandas as pd
from morph_lib.database import get_tables


def get_text_to_sql_prompt(
    prompt: str,
    connection: Optional[str] = None,
    table_names: List[str] = [],
    schema_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    table_structures = get_tables(table_names, schema_name, connection)
    table_structure_text = "\n\n".join(
        [table_structure.to_text() for table_structure in table_structures]
    )
    messages = [
        {
            "role": "system",
            "content": f"Below is the structure of a database table and its fields. The purpose is to answer questions from the user by issuing SQL to these tables. Please generate SQL according to the user's question.\n{table_structure_text}",
        }
    ]
    messages.append({"role": "user", "content": prompt})

    return messages


def get_generate_python_code_system_prompt() -> str:
    return """You are a great data analyst using python.
You can generate python code based on user prompt and you can use given python libraries.
Please generate python code using plotly or matplotlib for visualization and pandas based on the user's question.
"""


def get_generate_visualization_code_base_prompt(
    lib: Literal["plotly", "matplotlib"], df: pd.DataFrame
) -> str:
    libraries = [
        "pandas=2.1.3",
        "numpy=1.26.4",
        "urllib3==1.26.18",
        "requests=2.31.0",
    ]
    if lib == "plotly":
        libraries.append("plotly==5.18.0")
    elif lib == "matplotlib":
        libraries.append("matplotlib==3.5.2")
    library_prompts = "\n".join([f"- {library}" for library in libraries])
    data = df.head(5).to_markdown()

    prompt = f"""Generate Python3.9 code for visualization using pandas, {lib} and you should follow user's question.
Make sure to write `import pandas as pd` at the beginning of the code otherwise the code must throw errors.

## Rules:
1. You must generate Python code using {lib} for visualization and the code should return {lib} object.
2. You must use the given data for visualization.
3. You must use following code block and use additional packages if needed but do not change original import statements.
4. Function name is `main` and it should accept a pandas DataFrame as an argument.

This is the template you should follow:

```python
import pandas as pd # DO NOT FORGET TO IMPORT PANDAS

def main(df: pd.DataFrame):
    # Your code here
    return {lib} object
```

## Importable libraries:
{library_prompts}

But you may have other packages installed in the environment. So you can use other packages if needed.

## Data:
Given sample data is below. You need to use this data as data schema only.
DO NOT write contents of this data to the code. The df is always passed as an argument to the main function.

{data}
"""
    return prompt
