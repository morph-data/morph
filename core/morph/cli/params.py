import ast
import json
import re
from typing import Any

import click

log_format = click.option(
    "--log-format",
    envvar="MORPH_LOG_FORMAT",
    help="Specify the format of logging to the console and the log file. Use --log-format-file to configure the format for the log file differently than the console.",
    type=click.Choice(["text", "debug", "json", "default"], case_sensitive=False),
    default="default",
)


def parse_key_value(ctx, param, value):
    data_dict: dict[str, Any] = {}

    def format_to_json(val: str) -> str:
        def add_quotes(match):
            key, val = match.groups()
            key = key.strip()
            val = val.strip()
            return f'"{key}": "{val}"'

        formatted = re.sub(r"\{(\w+):(\w+)\}", lambda m: "{" + add_quotes(m) + "}", val)
        return formatted

    def convert_value(val: str) -> Any:
        if val.lower() == "true":
            return True
        elif val.lower() == "false":
            return False
        if val.isdigit():
            return int(val)
        try:
            return float(val)
        except ValueError:
            pass

        if val.startswith("[") and val.endswith("]"):
            try:
                parsed_list = json.loads(val.replace("'", '"'))
                if isinstance(parsed_list, list):
                    return parsed_list
            except json.JSONDecodeError:
                pass

            try:
                parsed_list = ast.literal_eval(val)
                if isinstance(parsed_list, list):
                    return parsed_list
            except (ValueError, SyntaxError):
                pass

        if re.match(r"\{(\w+):(\w+)\}", val):
            val = format_to_json(val)
        try:
            parsed_json = json.loads(val)
            if isinstance(parsed_json, dict):
                return parsed_json
        except json.JSONDecodeError:
            pass
        try:
            parsed_dict = ast.literal_eval(val)
            if isinstance(parsed_dict, dict):
                return parsed_dict
        except (ValueError, SyntaxError):
            pass

        return val

    for item in value:
        try:
            key, val = item.split("=", 1)
            data_dict[key.strip()] = convert_value(val.strip())
        except ValueError:
            raise click.BadParameter(f"'{item}' is not a valid key=value pair")

    return data_dict


data = click.option(
    "-d",
    "--data",
    multiple=True,
    callback=parse_key_value,
    help="Key-value pairs in the form key=value",
)

run_id = click.option(
    "--run-id",
    "-c",
    help="Specify the run id.",
)

canvas = click.option("--canvas", "-c", help="Specify the canvas name.")

dag = click.option(
    "--dag",
    is_flag=True,
    help="Run as a Directed Acyclic Graph (DAG).",
)

no_cache = click.option(
    "--no-cache",
    is_flag=True,
    help="Do not use the cache.",
)


is_debug = click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode.",
)

dry_run = click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    help="Perform a dry run without executing the tasks.",
)

verbose = click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose mode.",
)

file = click.option(
    "--file",
    "-f",
    type=click.Path(exists=True),
    help="Specify the path to the resource.",
)

alias = click.option(
    "--alias",
    "-a",
    type=str,
    help="Specify the alias of the resource.",
)

all = click.option(
    "--all",
    is_flag=True,
    help="Select all resources.",
)

connection = click.option(
    "--connection",
    "-c",
    type=str,
    help="Specify the connection slug.",
)


output_paths = click.option(
    "--output-paths",
    "-o",
    type=click.Path(exists=False),
    multiple=True,
    help="Specify the output paths.",
)

parent_output_path = click.option(
    "--parent-output-path",
    "-po",
    multiple=True,
    callback=parse_key_value,
    help="Key-value pairs in the form key=value",
)

tmp = click.option(
    "--tmp",
    is_flag=True,
    help="Whether to save output to a temporary file.",
)

template = click.option(
    "--template",
    "-t",
    type=str,
    required=True,
    help="Specify the path or alias to the template.",
)

stream = click.option(
    "--stream",
    is_flag=True,
    help="Whether to echo streaming output.",
)

port = click.option(
    "--port",
    "-p",
    type=int,
    help="API Server port.",
    default=9002,
)

host = click.option(
    "--host",
    "-h",
    type=str,
    help="API Server Host.",
    default="0.0.0.0",
)

restart = click.option(
    "--restart",
    is_flag=True,
    help="Whether to restart API server.",
)

workdir = click.option(
    "--workdir",
    type=str,
    help="Specify the project workdir.",
)

stop = click.option(
    "--stop",
    is_flag=True,
    help="Whether to stop API server.",
)

build = click.option(
    "--build",
    is_flag=True,
    help="Whether to build front code.",
)

profile = click.option(
    "--profile",
    type=str,
    help="Specify the profile name.",
)

no_log = click.option(
    "--no-log",
    is_flag=True,
    help="Whether to disable logging.",
)
