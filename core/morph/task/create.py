import os.path
import re
import sys
from pathlib import Path
from typing import Optional

import click

from morph import MorphGlobalContext
from morph.cli.flags import Flags
from morph.task.base import BaseTask
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.template.inspection import MorphTemplateLanguage


def to_snake_case(text):
    text = re.sub("([A-Z]+)", r"_\1", text)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    snake_case_text = (
        text.lower().strip("_").replace(" ", "_").replace("__", "_").replace("-", "_")
    )
    return snake_case_text


class CreateTask(BaseTask):
    def __init__(self, args: Flags, force: bool = False):
        super().__init__(args)
        self.args = args
        self.force = force

    def run(self):
        try:
            project_root = find_project_root_dir()
        except FileNotFoundError as e:
            click.echo(click.style(f"Error: {str(e)}", fg="red"))
            raise e

        filename: Path = Path(self.args.FILENAME)
        template: Optional[str] = self.args.TEMPLATE or None
        name: str = self.args.NAME or to_snake_case(filename.stem)
        description: str = (
            self.args.DESCRIPTION or "Auto-generated via morph-cli template."
        )
        parent_name: Optional[str] = self.args.PARENT_NAME or None
        connection: Optional[str] = self.args.CONNECTION or None

        # Validate filename
        if filename.is_file():
            click.echo(
                click.style(
                    f'Error: specified file "{filename.as_posix()}" already exists.',
                    fg="red",
                )
            )
            sys.exit(1)

        # Retrieve template code
        language: MorphTemplateLanguage = MorphTemplateLanguage.PYTHON
        ext = "".join(filename.suffixes)
        if ext == ".py":
            language = MorphTemplateLanguage.PYTHON
            if not template:
                template = (
                    "transform_cell_result"
                    if parent_name
                    else "python_starter_template"
                )
        elif ext == ".sql":
            language = MorphTemplateLanguage.SQL
            template = template or "sql_starter_template"
        elif ext == ".vg.json":
            language = MorphTemplateLanguage.JSON
            if template:
                click.echo(
                    click.style(
                        f'Warning: template option is ignored for "*{ext}" files.',
                        fg="red",
                    )
                )
            template = "vg_json_template"
        elif ext == ".mdx":
            language = MorphTemplateLanguage.MDX
            template = template or "mdx_starter_template"

        template_code = ""
        if template:
            if Path(template).is_file():
                local_template = (
                    Path(template)
                    if Path(template).is_absolute()
                    else Path(project_root) / template
                )
                if not local_template.exists():
                    click.echo(
                        click.style(
                            f'Error: specified local template "{local_template.as_posix()}" does not exist.',
                            fg="red",
                        )
                    )
                    sys.exit(1)
                template_code = local_template.read_text()
            else:
                # Search morph-cli global template
                global_template_path = Path(os.path.dirname(__file__)).joinpath(
                    f"utils/template/scaffold/{language.value}/{template}{ext}"
                )
                global_code = (
                    global_template_path.read_text()
                    if global_template_path.exists()
                    else None
                )

                if global_code:
                    template_code = global_code
                else:
                    click.echo(
                        click.style(
                            f'Error: specified global template "{template}" does not exist.',
                            fg="red",
                        )
                    )
                    sys.exit(2)  # 2: Misuse of shell builtins

        # Replace placeholders in template code according to other arguments
        # - name: {MORPH_NAME} and "def main("
        template_code = template_code.replace("{MORPH_NAME}", name)
        template_code = template_code.replace("def main(", f"def {name}(")
        # - description: {MORPH_DESCRIPTION}
        template_code = template_code.replace("{MORPH_DESCRIPTION}", description)
        # - parent_name: {MORPH_PARENT_NAME}
        template_code = template_code.replace("{MORPH_PARENT_NAME}", parent_name or "")
        # - connection: {MORPH_CONNECTION}
        if connection:
            template_code = template_code.replace("{MORPH_CONNECTION}", connection)
        else:
            template_code = template_code.replace(
                'connection="{MORPH_CONNECTION}"', "connection=None"
            )

        # Write the template code to the file
        with open(filename.as_posix(), "w") as f:
            f.write(template_code)

        # Compile the project
        context = MorphGlobalContext.get_instance()
        errors = context.load(project_root)
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
                    "Error: Please check your options and try again.",
                    fg="red",
                    bg="yellow",
                )
            )
            os.remove(filename.as_posix())
        else:
            context.dump()
