import base64
import io
from typing import Any, Dict, Literal, Optional, Union

import pandas as pd
from PIL import Image


def convert_file_output(
    type: Literal["json", "html", "image", "markdown"],
    output_path: str,
    ext: str,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
) -> Union[str, Dict[str, Any]]:
    if type == "json":
        if ext == "csv":
            chunks = []
            for chunk in pd.read_csv(
                output_path,
                header=0,
                chunksize=1_000_000,
                encoding_errors="replace",
                sep=",",
            ):
                chunks.append(chunk)
            df = pd.concat(chunks, axis=0)
        elif ext == "parquet":
            df = pd.read_parquet(output_path)
        count = len(df)
        limit = limit if limit is not None else len(df)
        skip = skip if skip is not None else 0
        df = df.iloc[skip : skip + limit]
        return {"count": count, "items": df.to_dict(orient="records")}
    elif type == "html" or type == "markdown":
        with open(output_path, "r") as f:
            return f.read()
    elif type == "image":
        with open(output_path, "rb") as f:
            image = Image.open(f)
            image.load()
        buffered = io.BytesIO()
        image.save(buffered, format=image.format)
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return img_base64


def convert_vg_json_to_html(vg_json: str) -> str:
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
    <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
    </head>
    <body>
    <div id="vis"></div>
    <script type="text/javascript">
        var spec = {vg_json};
        vegaEmbed('#vis', spec);
    </script>
    </body>
    </html>
    """
    return html_template.replace("\n", "")


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
