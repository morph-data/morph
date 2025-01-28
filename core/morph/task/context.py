import os
import sys
from pathlib import Path

import click

from morph.api.cloud.client import MorphApiKeyClientImpl
from morph.api.cloud.types import UserInfo
from morph.cli.flags import Flags
from morph.config.project import load_project
from morph.task.base import BaseTask
from morph.task.utils.morph import find_project_root_dir


class ContextTask(BaseTask):
    def __init__(self, args: Flags):
        super().__init__(args)
        self.args = args
        self.output = self.args.OUTPUT

        try:
            self.project_root = find_project_root_dir(os.getcwd())
        except FileNotFoundError as e:
            click.echo(click.style(f"Error: {str(e)}", fg="red"))
            sys.exit(1)

        project = load_project(self.project_root)
        if not project:
            click.echo(click.style("Project configuration not found.", fg="red"))
            sys.exit(1)
        elif project.project_id is None:
            click.echo(
                click.style(
                    "Error: No project id found. Please fill project_id in morph_project.yml.",
                    fg="red",
                )
            )
            sys.exit(1)

        try:
            self.client = MorphApiKeyClientImpl()
        except ValueError as e:
            click.echo(click.style(f"Error: {str(e)}", fg="red"))
            sys.exit(1)

    def run(self):
        res = self.client.verify_api_secret()
        if res.is_error():
            click.echo(click.style("Error: Could not find user info.", fg="red"))
            sys.exit(1)
        response_json = res.json()
        if "user" not in response_json:
            click.echo(click.style("Error: Could not find user info.", fg="red"))
            sys.exit(1)

        if self.output:
            if Path(self.output).parent != Path("."):
                os.makedirs(os.path.dirname(self.output), exist_ok=True)
            with open(self.output, "w") as f:
                f.write(UserInfo(**response_json["user"]).model_dump_json(indent=4))
        else:
            click.echo(UserInfo(**response_json["user"]).model_dump_json(indent=4))
