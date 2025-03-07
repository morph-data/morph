import json
import sys
from pathlib import Path
from typing import List

import click
import pydantic

from morph.cli.flags import Flags
from morph.config.project import load_project
from morph.task.base import BaseTask
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.run_backend.inspection import get_checksum
from morph.task.utils.run_backend.state import (
    MorphFunctionMetaObjectCacheManager,
    MorphGlobalContext,
)


class CompileTask(BaseTask):
    def __init__(self, args: Flags, force: bool = False):
        super().__init__(args)
        self.args = args
        self.force = force

    def run(self):
        try:
            project_root = find_project_root_dir()
        except FileNotFoundError as e:
            click.echo(click.style(str(e), fg="red"))
            raise e

        try:
            cache = MorphFunctionMetaObjectCacheManager().get_cache()
        except (pydantic.ValidationError, json.decoder.JSONDecodeError):
            click.echo(
                click.style(
                    "Warning: Morph-cli project cache is corrupted. Recompiling...",
                    fg="yellow",
                )
            )
            cache = None

        if cache is None:
            needs_compile = True
        elif len(cache.errors) > 0:
            needs_compile = True
        else:
            needs_compile = False
            project = load_project(project_root)
            if project is not None:
                source_paths = project.source_paths
            else:
                source_paths = []

            extra_paths: List[str] = []
            compare_dirs = []
            if len(source_paths) == 0:
                compare_dirs.append(Path(project_root))
            else:
                for source_path in source_paths:
                    compare_dirs.append(Path(f"{project_root}/{source_path}"))

            for epath in extra_paths:
                epath_p = Path(epath)
                if not epath_p.exists() or not epath_p.is_dir():
                    continue
                compare_dirs.append(epath_p)

            for compare_dir in compare_dirs:
                if cache.directory_checksums.get(
                    compare_dir.as_posix(), ""
                ) != get_checksum(Path(compare_dir)):
                    needs_compile = True
                    break

        if self.force:
            needs_compile = True

        if needs_compile:
            context = MorphGlobalContext.get_instance()
            errors = context.load(project_root)
            context.dump()

            if len(errors) > 0:
                for error in errors:
                    click.echo(
                        click.style(
                            f"""Error occurred in {error.file_path}:{error.name} [{error.category}] {error.error}""",
                            fg="red",
                        )
                    )
                click.echo(
                    click.style(
                        "Error: Failed to compile morph project.", fg="red", bg="yellow"
                    ),
                    err=True,
                )
                sys.exit(1)

        if self.args.VERBOSE:
            info: dict = {
                "needs_compile": needs_compile,
            }
            if needs_compile:
                info["errors"] = errors
            elif cache is not None:
                info["errors"] = cache.errors

            click.echo(json.dumps(info, indent=2))

        click.echo(click.style("Successfully compiled! 🎉", fg="green"))
