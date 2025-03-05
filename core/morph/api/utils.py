import json
import sys
from typing import Any, Dict, Literal, Optional, Union

import pandas as pd
from morph_lib.types import HtmlResponse, MarkdownResponse

from morph.task.utils.run_backend.output import StreamChatResponse


def convert_file_output(
    type: Literal["json", "html", "markdown"],
    output: Any,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
) -> Union[str, Dict[str, Any], Any]:
    transformed_output: Any = output

    if type == "json":
        if isinstance(output, pd.DataFrame) or (
            hasattr(output, "__class__")
            and output.__class__.__name__.endswith("DataFrame")
        ):
            df = transformed_output
            count = len(df)
            limit = limit if limit is not None else len(df)
            skip = skip if skip is not None else 0
            df = df.iloc[skip : skip + limit]
            df = df.replace({float("nan"): None, pd.NaT: None}).to_dict(
                orient="records"
            )
            return {"count": count, "items": df}
        elif isinstance(output, dict) or isinstance(output, list):
            transformed_output = json.dumps(output, indent=4, ensure_ascii=False)
        elif isinstance(output, StreamChatResponse):
            transformed_output = json.dumps(
                output.model_dump(), indent=4, ensure_ascii=False
            )
        else:
            raise Exception(f"Invalid output type: type='json' value={output}")
    elif type == "html" or type == "markdown":
        if isinstance(output, HtmlResponse):
            return output.value
        elif isinstance(output, MarkdownResponse):
            return output.value
        else:
            return output
    raise Exception(f"Invalid output type: type={type}")


def convert_variables_values(variables: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if variables is None:
        return {}
    variables_: Dict[str, Any] = {}
    for k, v in variables.items():
        if isinstance(v, str):
            if v.isdigit():
                variables_[k] = int(v)
                continue
            try:
                f_v = float(v)
                variables_[k] = f_v
                continue
            except ValueError:
                pass
        variables_[k] = v
    return variables_


def set_command_args():
    if len(sys.argv) < 2:
        sys.argv = ["", "serve"]
