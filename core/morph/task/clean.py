import shutil
from pathlib import Path

import click

from morph.cli.flags import Flags
from morph.constants import MorphConstant
from morph.task.base import BaseTask
from morph.task.utils.morph import find_project_root_dir


class CleanTask(BaseTask):
    def __init__(self, args: Flags, force: bool = False):
        super().__init__(args)
        self.args = args

        try:
            self.project_root = find_project_root_dir()
        except FileNotFoundError as e:
            click.echo(click.style(str(e), fg="red"))
            raise e

        self.clean_dir = Path(self.project_root).joinpath(".morph")
        self.frontend_dir = Path(MorphConstant.frontend_dir(self.project_root))

    def run(self):
        verbose = self.args.VERBOSE

        if self.clean_dir.exists():
            # Iterate through the contents of .morph and delete all except frontend
            for item in self.clean_dir.iterdir():
                if item.resolve() == self.frontend_dir.resolve():  # Compare as Path
                    if verbose:
                        click.echo(
                            click.style(
                                f"Skipping directory {self.frontend_dir}...",
                                fg="yellow",
                            )
                        )
                    continue

                if verbose:
                    click.echo(click.style(f"Removing {item}...", fg="yellow"))

                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()

            # Ensure the .morph directory exists even if emptied
            self.clean_dir.mkdir(parents=True, exist_ok=True)
        else:
            if verbose:
                click.echo(
                    click.style(f"Directory {self.clean_dir} not found", fg="yellow")
                )

        click.echo(
            click.style(
                "Cache cleared! 🧹 Your workspace is fresh and ready.", fg="green"
            )
        )
