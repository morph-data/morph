import io
import os
import sys
import zipfile

import click
import requests

from morph.cli.flags import Flags
from morph.config.project import load_project
from morph.constants import MorphConstant
from morph.task.base import BaseTask
from morph.task.utils.morph import find_project_root_dir


class PluginTask(BaseTask):
    def __init__(self, args: Flags):
        super().__init__(args)
        self.args = args
        self.plugin_name: str = args.PLUGIN_NAME

        try:
            self.project_root = find_project_root_dir(os.getcwd())
        except FileNotFoundError as e:
            click.echo(click.style(f"Error: {str(e)}", fg="red"))
            sys.exit(1)

        project = load_project(self.project_root)
        if not project:
            click.echo(click.style("Project configuration not found.", fg="red"))
            sys.exit(1)

    def run(self):
        branch = "main"
        package_name = "morph-plugins"
        organization = "morph-data"
        plugin_git_url = f"https://github.com/{organization}/{package_name}"
        plugin_dir = os.path.join(self.project_root, MorphConstant.PLUGIN_DIR)
        zip_url = f"{plugin_git_url}/archive/refs/heads/{branch}.zip"

        try:
            response = requests.get(zip_url)
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                if not any(
                    file.startswith(f"{package_name}-{branch}/{self.plugin_name}/")
                    for file in zip_ref.namelist()
                ):
                    raise Exception(f"{self.plugin_name} not found in plugins.")
                for file in zip_ref.namelist():
                    if file.startswith(f"{package_name}-{branch}/{self.plugin_name}/"):
                        relative_path = file.replace(f"{package_name}-{branch}/", "", 1)
                        extract_path = os.path.join(plugin_dir, relative_path)

                        if file.endswith("/"):
                            os.makedirs(extract_path, exist_ok=True)
                            continue

                        os.makedirs(os.path.dirname(extract_path), exist_ok=True)

                        with zip_ref.open(file) as source, open(
                            extract_path, "wb"
                        ) as target:
                            target.write(source.read())
        except Exception as e:
            click.echo(
                click.style(
                    f"Error: {str(e)}\nFailed to fetch plugin {self.plugin_name}.",
                    fg="red",
                )
            )
            sys.exit(1)

        click.echo(
            click.style(
                f"✅ Plugin {self.plugin_name} has been added to {plugin_dir}/{self.plugin_name}/.",
                fg="green",
            )
        )
