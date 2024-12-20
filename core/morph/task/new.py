import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
import git

from morph import MorphGlobalContext
from morph.api.cloud.utils import is_cloud
from morph.cli.flags import Flags
from morph.config.project import default_initial_project, load_project, save_project
from morph.constants import MorphConstant
from morph.task.base import BaseTask
from morph.task.utils.connection import ConnectionYaml
from morph.task.utils.sqlite import SqliteDBManager


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
        # Validate workspace template options
        github_url = self.args.GITHUB_URL
        directory = self.args.DIRECTORY
        branch = self.args.BRANCH
        if (github_url and not directory) or (not github_url and directory):
            click.echo(
                click.style(
                    "Both --github-url and --directory must be specified together.",
                    fg="red",
                    bg="yellow",
                )
            )
            sys.exit(2)  # 2: Misuse of shell builtins

        if not is_cloud() and not github_url and not directory:
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

            # Initialize the project database
            db_manager = SqliteDBManager(self.project_root)
            db_manager.initialize_database()

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

            connection_yaml = ConnectionYaml.load_yaml()
            if len(list(connection_yaml.connections.keys())) > 0:
                default_connection = list(connection_yaml.connections.keys())[0]
                project = load_project(self.project_root)
                if project is None:
                    project = default_initial_project()
                project.default_connection = default_connection
                save_project(self.project_root, project)

            os.chdir(original_working_dir)
        else:
            # Apply default template if no options are specified
            github_url = (
                github_url or "https://github.com/useMorph/workspace-template.git"
            )
            directory = directory or "template/morph-starter"

            if not github_url.startswith("http"):
                click.echo(
                    click.style(
                        "--github-url must be a valid URL starting with 'http' or 'https'. Other protocols are not supported.",
                        fg="red",
                        bg="yellow",
                    )
                )
                sys.exit(2)  # 2: Misuse of shell builtins

            click.echo("Creating new Morph project...")

            # Create the project structure
            if not os.path.exists(self.project_root):
                os.makedirs(self.project_root, exist_ok=True)

            # Clone the workspace template
            click.echo(f"Cloning workspace template from {github_url}...")
            clone_dir = Path(f"/tmp/{os.path.split(github_url)[-1]}")
            if os.path.exists(clone_dir.as_posix()):
                shutil.rmtree(clone_dir.as_posix())
            try:
                git.Repo.clone_from(
                    github_url,
                    clone_dir.as_posix(),
                    branch=branch,
                    depth=1,
                    single_branch=True,
                )
            except git.exc.GitCommandError as e:
                click.echo(
                    click.style(
                        f"Failed to clone the workspace template from {github_url}",
                        fg="red",
                        bg="yellow",
                    )
                )

                if e.stderr:
                    git_err_msg = e.stderr.strip().strip("'")
                    if git_err_msg.startswith("stderr: "):
                        git_err_msg = git_err_msg[len("stderr: ") :]
                    click.echo(click.style(git_err_msg, fg="red"))
                sys.exit(1)  # 1: General errors

            # Apply the template to the project directory
            click.echo(f"Applying {directory} template to {self.project_root}...")
            try:
                subprocess.run(
                    f"cp -r {clone_dir.joinpath(directory).as_posix()}/. {self.project_root}",
                    shell=True,
                    check=True,
                )
            except subprocess.CalledProcessError:
                click.echo(
                    click.style(
                        f"Failed to apply {directory} template. Please check your directory structure of workspace template.",
                        fg="red",
                        bg="yellow",
                    )
                )
                sys.exit(1)  # 1: General errors

            # Add 'file_upload' python file
            file_upload_python_path = f"{self.project_root}/src/utils/file_upload.py"
            file_upload_python_content = """\
import os
import morph
from morph import MorphGlobalContext

# Morph decorators
# The `@morph.func` decorator required to be recognized as a function in morph.
# For more information: https://docs.morph-data.io
@morph.func(
    name="file_upload",
)
@morph.variables("file")
def file_upload(context: MorphGlobalContext) -> str:
    # Retrieve the `file` variable from the context (Expand `~` to the full path)
    filepath = os.path.expanduser(context.vars["file"])
    filename = os.path.basename(filepath)

    # Check if the file exists
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    # Create the uploaded-files directory if it doesn't exist
    # NOTE: Make sure to use an absolute path for the directory
    upload_dir = os.path.abspath("uploaded-files/")
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)

    # Read the content of the file in binary mode
    with open(filepath, "rb") as f:
        file_content = f.read()

    # Save the content to the uploaded-files directory in binary mode
    saved_filepath = os.path.join(upload_dir, filename)
    with open(saved_filepath, "wb") as f:
        f.write(file_content)

    return saved_filepath
    """
            if not os.path.exists(file_upload_python_path):
                file_upload_python_dir = os.path.dirname(file_upload_python_path)
                if not os.path.exists(file_upload_python_dir):
                    os.makedirs(file_upload_python_dir)
                with open(file_upload_python_path, "w") as f:
                    f.write(file_upload_python_content)

            db_path = f"{self.project_root}/morph_project.sqlite3"
            if not os.path.exists(db_path):
                with open(db_path, "w") as f:
                    f.write("")

            # Initialize the project database
            db_manager = SqliteDBManager(self.project_root)
            db_manager.initialize_database()

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

            os.chdir(original_working_dir)

        click.echo(click.style("Project setup completed successfully! 🎉", fg="green"))

        return True
