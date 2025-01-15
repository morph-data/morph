import os
import shutil
from pathlib import Path
from typing import Optional

import click

from morph.cli.flags import Flags
from morph.config.project import default_initial_project, load_project, save_project
from morph.constants import MorphConstant
from morph.task.base import BaseTask
from morph.task.utils.connection import ConnectionYaml
from morph.task.utils.run_backend.state import MorphGlobalContext


class NewTask(BaseTask):
    def __init__(self, args: Flags, project_directory: Optional[str]):
        super().__init__(args)
        self.args = args

        if not project_directory:
            project_directory = input("What is your project name? ")
        self.project_root = project_directory

        # initialize the morph directory
        morph_dir = MorphConstant.INIT_DIR
        if not os.path.exists(morph_dir):
            os.makedirs(morph_dir)
            click.echo(f"Created directory at {morph_dir}")

    def run(self):
        click.echo("Creating new Morph project...")

        if not os.path.exists(self.project_root):
            os.makedirs(self.project_root, exist_ok=True)

        click.echo(f"Applying template to {self.project_root}...")

        templates_dir = (
            Path(__file__).parents[1].joinpath("include", "starter_template")
        )
        for root, _, template_files in os.walk(templates_dir):
            rel_path = os.path.relpath(root, templates_dir)
            target_path = os.path.join(self.project_root, rel_path)

            os.makedirs(target_path, exist_ok=True)

            for template_file in template_files:
                src_file = os.path.join(root, template_file)
                dest_file = os.path.join(target_path, template_file)
                shutil.copy2(src_file, dest_file)

        db_path = f"{self.project_root}/morph_project.sqlite3"
        if not os.path.exists(db_path):
            with open(db_path, "w") as f:
                f.write("")

        # Execute the post-setup tasks
        original_working_dir = os.getcwd()
        os.chdir(self.project_root)
        self.project_root = (
            os.getcwd()
        )  # This avoids compile errors in case the project root is symlinked

        # Compile the project
        context = MorphGlobalContext.get_instance()
        context.load(self.project_root)
        context.dump()

        project = load_project(self.project_root)
        if project is None:
            project = default_initial_project()
        if self.args.PROJECT_ID:
            project.project_id = self.args.PROJECT_ID

        connection_yaml = ConnectionYaml.load_yaml()
        if len(list(connection_yaml.connections.keys())) > 0:
            default_connection = list(connection_yaml.connections.keys())[0]
            project.default_connection = default_connection

        save_project(self.project_root, project)

        os.chdir(original_working_dir)

        click.echo(click.style("Project setup completed successfully! 🎉", fg="green"))

        return True
