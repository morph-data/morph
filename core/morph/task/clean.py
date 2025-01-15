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

        if clean_dir.exists():
            # Delete the entire .morph directory
            if verbose:
                click.echo(
                    click.style(f"Removing directory {clean_dir}...", fg="yellow")
                )
            shutil.rmtree(clean_dir)

            # Recreate the empty .morph directory
            clean_dir.mkdir(parents=True, exist_ok=True)
            if verbose:
                click.echo(
                    click.style(f"Recreated empty directory {clean_dir}", fg="yellow")
                )
        else:
            if verbose:
                click.echo(click.style(f"Directory {clean_dir} not found", fg="yellow"))

        click.echo(
            click.style(
                "Cache cleared! 🧹 Your workspace is fresh and ready.", fg="green"
            )
        )
