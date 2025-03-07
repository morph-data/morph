from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, List, Literal, cast

import click
import pydantic

from morph.cli.flags import Flags
from morph.config.project import load_project
from morph.task.base import BaseTask
from morph.task.utils.morph import Resource, find_project_root_dir
from morph.task.utils.run_backend.inspection import get_checksum
from morph.task.utils.run_backend.state import (
    MorphFunctionMetaObjectCacheManager,
    MorphGlobalContext,
)


class PrintResourceTask(BaseTask):
    def __init__(self, args: Flags):
        super().__init__(args)
        self.args = args

        target: str
        target_type: Literal["alias", "file", "all"]
        if args.ALL:
            target = ""
            target_type = "all"
        elif args.ALIAS:
            target = args.ALIAS
            target_type = "alias"
        elif args.FILE:
            target = args.FILE
            target_type = "file"
        else:
            click.echo("Either --alias, --file or --all must be provided.")
            raise click.Abort()

        self.target = target
        self.target_type = target_type

        try:
            self.project_root = find_project_root_dir()
        except FileNotFoundError as e:
            click.echo(click.style(str(e), fg="red"))
            raise e

    def run(self):
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

        output: dict[str, Any] = {}
        if cache is None:
            needs_compile = True
        elif len(cache.errors) > 0:
            needs_compile = True
        else:
            needs_compile = False
            project = load_project(self.project_root)
            if project is not None:
                source_paths = project.source_paths
            else:
                source_paths = []
            extra_paths: List[str] = []
            compare_dirs = []
            if len(source_paths) == 0:
                compare_dirs.append(Path(self.project_root))
            else:
                for source_path in source_paths:
                    compare_dirs.append(Path(f"{self.project_root}/{source_path}"))

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

        if needs_compile or cache is None:
            context = MorphGlobalContext.get_instance()
            errors = context.load(self.project_root)
            if len(errors) > 0:
                output["errors"] = [error.model_dump() for error in errors]
            cache = context.dump()
        elif cache is not None and len(cache.errors) > 0:
            output["errors"] = [error.model_dump() for error in cache.errors]

        if self.target_type == "all":
            resource_dicts: list[dict] = []
            for item in cache.items:
                # id is formatted as {filename}:{function_name}
                if not item.spec.id or not item.spec.name:
                    continue

                if sys.platform == "win32":
                    if len(item.spec.id.split(":")) > 2:
                        filepath = (
                            item.spec.id.rsplit(":", 1)[0] if item.spec.id else ""
                        )
                    else:
                        filepath = item.spec.id if item.spec.id else ""
                else:
                    filepath = item.spec.id.split(":")[0]
                resource_item = Resource(
                    alias=item.spec.name,
                    path=filepath,
                    connection=(item.spec.connection if item.spec.connection else None),
                    data_requirements=(
                        cast(list, item.spec.data_requirements)
                        if item.spec.data_requirements
                        else None
                    ),
                )
                resource_dicts.append(resource_item.model_dump())

            output["resources"] = resource_dicts
            click.echo(json.dumps(output, indent=2))
        elif self.target_type == "alias":
            # NOTE: use Resource entity to keep backward compatibility with old output format
            resource: Resource | None = None
            for item in cache.items:
                if item.spec.name == self.target:
                    # id is formatted as {filename}:{function_name}
                    if not item.spec.id or not item.spec.name:
                        continue
                    filepath = item.spec.id.split(":")[0]
                    resource = Resource(
                        alias=item.spec.name,
                        path=filepath,
                        connection=(
                            item.spec.connection if item.spec.connection else None
                        ),
                        data_requirements=(
                            cast(list, item.spec.data_requirements)
                            if item.spec.data_requirements
                            else None
                        ),
                    )
                    break
            if resource:
                output["resources"] = [resource.model_dump()]
                click.echo(json.dumps(output, indent=2))
            else:
                click.echo(f"Alias {self.target} not found.")
        elif self.target_type == "file":
            abs_path = Path(self.target).as_posix()
            resource = None
            for item in cache.items:
                # id is formatted as {filename}:{function_name}
                if not item.spec.id or not item.spec.name:
                    continue
                filepath = item.spec.id.split(":")[0]
                if filepath == abs_path:
                    resource = Resource(
                        alias=item.spec.name,
                        path=filepath,
                        connection=(
                            item.spec.connection if item.spec.connection else None
                        ),
                        data_requirements=(
                            cast(list, item.spec.data_requirements)
                            if item.spec.data_requirements
                            else None
                        ),
                    )
                    break
            if resource:
                output["resources"] = [resource.model_dump()]
                click.echo(json.dumps(output, indent=2))
            else:
                click.echo(f"File {self.target} not found.")
