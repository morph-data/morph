import json
from pathlib import Path

import click

from morph.cli.flags import Flags
from morph.config.project import load_project
from morph.task.base import BaseTask
from morph.task.utils.knowledge.inspection import get_checksum
from morph.task.utils.knowledge.state import MorphKnowledgeManager, load_cache
from morph.task.utils.morph import find_project_root_dir


class CompileKnowledgeTask(BaseTask):
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

        cache = load_cache(project_root)
        if cache is None:
            needs_compile = True
        else:
            needs_compile = False
            project = load_project(project_root)
            if project is not None:
                knowledge_paths = project.knowledge_paths
            else:
                knowledge_paths = []

            compare_dirs = []
            if len(knowledge_paths) == 0:
                compare_dirs.append(Path(project_root))
            else:
                for knowledge_path in knowledge_paths:
                    compare_dirs.append(Path(f"{project_root}/{knowledge_path}"))

            for compare_dir in compare_dirs:
                if cache.directory_checksums.get(
                    compare_dir.as_posix(), ""
                ) != get_checksum(Path(compare_dir)):
                    needs_compile = True
                    break

        if self.force:
            needs_compile = True

        if needs_compile:
            manager = MorphKnowledgeManager.get_instance()
            errors = manager.load(project_root)
            manager.dump()

            if len(errors) > 0:
                click.echo(
                    click.style("Error: Failed to load morph knowledge.", fg="red")
                )
                for error in errors:
                    click.echo(
                        click.style(
                            f"""Error occurred in {error.file_path}:{error.name} [{error.category}] {error.error}""",
                            fg="red",
                        )
                    )

        if self.args.VERBOSE:
            info: dict = {
                "needs_compile": needs_compile,
            }
            if needs_compile:
                info["errors"] = errors
            elif cache is not None:
                info["errors"] = cache.errors

            click.echo(json.dumps(info, indent=2))
