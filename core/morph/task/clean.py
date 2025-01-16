import shutil
from pathlib import Path

import click

from morph.cli.flags import Flags
from morph.task.base import BaseTask
from morph.task.utils.morph import find_project_root_dir


class CleanTask(BaseTask):
    def __init__(self, args: Flags, force: bool = False):
        super().__init__(args)
        self.args = args

    def run(self):
        verbose = self.args.VERBOSE

        try:
            project_root = find_project_root_dir()
        except FileNotFoundError as e:
            click.echo(click.style(str(e), fg="red"))
            raise e

        clean_dir = Path(project_root).joinpath(".morph")
        clean_files = ["meta.json", "knowledge.json", "template.json"]
        clean_directories = ["frontend"]

        for _f in clean_files:
            clean_file = clean_dir.joinpath(_f)
            if clean_file.exists():
                if verbose:
                    click.echo(click.style(f"Removing {clean_file}", fg="yellow"))
                clean_file.unlink()
            else:
                if verbose:
                    click.echo(click.style(f"File {clean_file} not found", fg="yellow"))

        for _d in clean_directories:
            clean_directory = clean_dir.joinpath(_d)
            if clean_directory.exists():
                if verbose:
                    click.echo(click.style(f"Removing {clean_directory}", fg="yellow"))
                shutil.rmtree(clean_directory)
            else:
                if verbose:
                    click.echo(
                        click.style(
                            f"Directory {clean_directory} not found", fg="yellow"
                        )
                    )

        click.echo(
            click.style(
                "Cache cleared! 🧹 Your workspace is fresh and ready.", fg="green"
            )
        )
