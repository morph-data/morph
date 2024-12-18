from __future__ import annotations

import click

from morph.cli.flags import Flags
from morph.task.base import BaseTask
from morph.task.utils.knowledge.inspection import (
    KnowledgeScanResult,
    MorphKnowledgeMetaObject,
    MorphKnowledgeMetaObjectSource,
)
from morph.task.utils.knowledge.state import MorphKnowledgeManager
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.run_backend.state import MorphGlobalContext


class FindKnowledgeTask(BaseTask):
    def __init__(
        self,
        args: Flags,
        select_source: bool = False,
        connection: str | None = None,
        type: str = "datasource",
    ):
        super().__init__(args)
        self.args = args
        self.select_source = select_source
        self.connection = connection
        self.type = type

    def run(self) -> KnowledgeScanResult | None:
        try:
            project_root = find_project_root_dir()
        except FileNotFoundError as e:
            click.echo(click.style(str(e), fg="red"))
            raise e

        manager = MorphKnowledgeManager.get_instance()
        errors = manager.load(project_root)

        if errors:
            click.echo(click.style("Failed to load knowledge.", fg="red"))
            for error in errors:
                click.echo(click.style(str(error), fg="red"))
            return None

        if self.select_source:
            result = manager.find_by_source(
                self.type,
                MorphKnowledgeMetaObjectSource(
                    name=self.args.KNOWLEDGE_NAME, connection=self.connection
                ),
            )
        else:
            result = manager.find(self.args.KNOWLEDGE_NAME)
        if result is not None:
            click.echo(result.model_dump_json(indent=2))
            return result

        context = MorphGlobalContext.get_instance()
        if self.args.NO_CACHE:
            errors = context.load(project_root)
        else:
            errors = context.partial_load(
                project_root,
                self.args.KNOWLEDGE_NAME,
            )
        if len(errors) > 0:
            click.echo(
                click.style(
                    f"Error: Failed to load morph functions [{errors}]", fg="red"
                )
            )
            click.Abort()

        if self.select_source is False or (self.select_source and self.type == "model"):
            resource = context.search_meta_object_by_name(self.args.KNOWLEDGE_NAME)
            if resource is not None:
                file_path = resource.id.split(":")[0]
                result = KnowledgeScanResult(
                    spec=MorphKnowledgeMetaObject(
                        id=resource.id,
                        name=resource.name,
                        type="model",
                        title=resource.title,
                        description=resource.description,
                        source=MorphKnowledgeMetaObjectSource(
                            name=resource.name,
                            connection=resource.connection,
                        ),
                        schemas=resource.schemas,
                        terms=resource.terms,
                    ),
                    file_path=file_path,
                    checksum="",
                )
                click.echo(result.model_dump_json(indent=2))
                return result

            if resource is None:
                click.echo(
                    click.style(
                        f"Knowledge '{self.args.KNOWLEDGE_NAME}' not found.", fg="red"
                    )
                )
                return None
        click.echo(
            click.style(f"Knowledge '{self.args.KNOWLEDGE_NAME}' not found.", fg="red")
        )
        return None
