import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click

from morph.cli.flags import Flags
from morph.config.project import default_initial_project, load_project, save_project
from morph.constants import MorphConstant
from morph.task.base import BaseTask
from morph.task.utils.morph import initialize_frontend_dir
from morph.task.utils.run_backend.state import MorphGlobalContext


class NewTask(BaseTask):
    def __init__(self, args: Flags, project_directory: Optional[str]):
        super().__init__(args)
        self.is_development = os.environ.get("MORPH_DEVELOPMENT", False)
        self.args = args

        if not project_directory:
            project_directory = input("What is your project name? ")
        self.project_root = project_directory

        # initialize the morph directory
        morph_dir = MorphConstant.INIT_DIR
        if not os.path.exists(morph_dir):
            os.makedirs(morph_dir)
            click.echo(f"Created directory at {morph_dir}")

        # Initialize the frontend directory
        # Copy the frontend template to ~/.morph/frontend if it doesn't exist
        initialize_frontend_dir(self.project_root)

        # Select the Python version for the project
        self.selected_python_version = self._select_python_version()

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

        # Execute the post-setup tasks
        self.original_dir = os.getcwd()
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

        # Ask the user to select a package manager
        package_manager_options = {
            "1": "poetry",
            "2": "uv",
            "3": "pip",
        }
        click.echo()
        click.echo("Select a package manager for your project:")
        for key, value in package_manager_options.items():
            click.echo(click.style(f"{key}: {value}", fg="blue"))

        click.echo(
            click.style("Enter the number of your choice. (default is ["), nl=False
        )
        click.echo(click.style("1: poetry", fg="blue"), nl=False)
        click.echo(click.style("]): "), nl=False)
        package_manager_choice = input().strip()

        # Validate user input and set the package manager
        project.package_manager = package_manager_options.get(
            package_manager_choice, "poetry"
        )
        if project.package_manager not in package_manager_options.values():
            click.echo(
                click.style(
                    "Warning: Invalid package manager. Defaulting to 'poetry'.",
                    fg="yellow",
                )
            )
            project.package_manager = "poetry"

        save_project(self.project_root, project)

        # Generate the Dockerfile template
        template_dir = Path(__file__).parents[1].joinpath("include")
        docker_template_file = template_dir.joinpath("Dockerfile")
        if not docker_template_file.exists():
            click.echo(
                click.style(
                    f"Template file not found: {docker_template_file}", fg="red"
                )
            )
            click.echo()
            sys.exit(1)

        # Generate the Dockerfile with the selected Python version
        dockerfile_path = os.path.join(self.project_root, "Dockerfile")
        try:
            with docker_template_file.open("r", encoding="utf-8") as f:
                dockerfile_content = f.read()

            # Replace the placeholder with the selected Python version
            dockerfile_content = dockerfile_content.replace(
                "${MORPH_PYTHON_VERSION}", self.selected_python_version
            )

            # Write the updated Dockerfile to the project directory
            with open(dockerfile_path, "w") as output_file:
                output_file.write(dockerfile_content)
        except FileNotFoundError as e:
            click.echo(
                click.style(f"Error: Template Dockerfile not found: {e}", fg="red")
            )
            sys.exit(1)
        except IOError as e:
            click.echo(click.style(f"Error: Unable to write Dockerfile: {e}", fg="red"))
            sys.exit(1)

        try:
            morph_data_version = importlib.metadata.version("morph-data")
        except importlib.metadata.PackageNotFoundError:
            morph_data_version = None
            click.echo(
                click.style(
                    "No local 'morph-data' found. Using unpinned (no version).",
                    fg="yellow",
                )
            )

        # Handle dependencies based on package manager
        if project.package_manager == "poetry":
            click.echo(click.style("Initializing Poetry...", fg="blue"))
            try:
                # Prepare the dependency argument
                if self.is_development:
                    branch = self._get_current_git_branch() or "develop"
                    morph_data_dep = (
                        'morph-data = { git = "https://github.com/morph-data/morph.git", rev = "%s" }'
                        % branch
                    )
                else:
                    if morph_data_version:
                        morph_data_dep = f'morph-data = "{morph_data_version}"'
                    else:
                        morph_data_dep = "morph-data"

                # Generate the pyproject.toml content
                pyproject_content = self._generate_pyproject_toml(
                    project_name=os.path.basename(os.path.normpath(self.project_root)),
                    morph_data_dependency=morph_data_dep,
                )
                pyproject_path = Path(self.project_root) / "pyproject.toml"
                pyproject_path.write_text(pyproject_content, encoding="utf-8")

                click.echo(
                    click.style(
                        "Added 'morph-data' to pyproject.toml with 'morph-data'.",
                        fg="green",
                    )
                )
            except subprocess.CalledProcessError as e:
                click.echo(click.style(f"Poetry initialization failed: {e}", fg="red"))
                click.echo()
                sys.exit(1)
        elif project.package_manager == "uv":
            click.echo(click.style("Initializing uv...", fg="blue"))
            try:
                # Prepare the dependency argument
                if self.is_development:
                    branch = self._get_current_git_branch() or "develop"
                    morph_data_dep = (
                        "morph-data @ git+https://github.com/morph-data/morph.git@%s#egg=morph-data"
                        % branch
                    )
                else:
                    if morph_data_version:
                        morph_data_dep = f"morph-data=={morph_data_version}"
                    else:
                        morph_data_dep = "morph-data"

                # Generate the pyproject.toml content
                pyproject_content = self._generate_uv_pyproject_toml(
                    project_name=os.path.basename(os.path.normpath(self.project_root)),
                    morph_data_dependency=morph_data_dep,
                )
                pyproject_path = Path(self.project_root) / "pyproject.toml"
                pyproject_path.write_text(pyproject_content, encoding="utf-8")

                click.echo(
                    click.style(
                        "Added 'morph-data' to pyproject.toml with 'morph-data'.",
                        fg="green",
                    )
                )
            except subprocess.CalledProcessError as e:
                click.echo(click.style(f"Poetry initialization failed: {e}", fg="red"))
                click.echo()
                sys.exit(1)
        elif project.package_manager == "pip":
            click.echo(click.style("Generating requirements.txt...", fg="blue"))
            requirements_path = os.path.join(self.project_root, "requirements.txt")
            try:
                with open(requirements_path, "w") as f:
                    if self.is_development:
                        branch = self._get_current_git_branch() or "develop"
                        f.write(
                            f"git+https://github.com/morph-data/morph.git@{branch}#egg=morph-data\n"
                        )
                    else:
                        if morph_data_version:
                            f.write(f"morph-data=={morph_data_version}\n")
                        else:
                            f.write("morph-data\n")
                click.echo(
                    click.style(
                        "Created requirements.txt with 'morph-data'.",
                        fg="green",
                    )
                )
            except IOError as e:
                click.echo(
                    click.style(f"Failed to create requirements.txt: {e}", fg="red")
                )
                sys.exit(1)

        click.echo()
        click.echo(click.style("Project setup completed successfully! 🎉", fg="green"))
        return True

    def _get_current_git_branch(self) -> Optional[str]:
        """
        Safely get the current Git branch name.

        Returns:
            Optional[str]: The current branch name, or None if it cannot be determined.
        """
        try:
            # Run the git command to get the current branch name
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.original_dir,
                text=True,
            ).strip()
            return branch or None
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Return None if Git command fails or Git is not installed
            click.echo(
                click.style("Warning: Git not found or command failed.", fg="yellow")
            )
            return None

    @staticmethod
    def _select_python_version() -> str:
        """
        Prompt the user to select a Python version for the project setup.
        """
        supported_versions = ["3.9", "3.10", "3.11", "3.12"]
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}"

        if current_version not in supported_versions:
            click.echo(
                click.style(
                    f"Warning: Current Python version ({current_version}) is not officially supported.",
                    fg="yellow",
                )
            )

        click.echo()
        click.echo("Select the Python version for your project:")
        for idx, version in enumerate(supported_versions, start=1):
            if version == current_version:
                click.echo(click.style(f"{idx}: {version} (current)", fg="blue"))
            else:
                click.echo(f"{idx}: {version}")

        click.echo(
            click.style("Enter the number of your choice. (default is ["), nl=False
        )
        click.echo(click.style(f"{current_version}", fg="blue"), nl=False)
        click.echo(click.style("]): "), nl=False)

        version_choice = input().strip()

        try:
            selected_version = supported_versions[int(version_choice) - 1]
            print_version_warning = False
        except ValueError:
            # If the input is empty, default to the current Python version (No warning)
            selected_version = current_version
            print_version_warning = False
        except IndexError:
            # If the input is invalid, default to the current Python version (with warning)
            selected_version = current_version
            print_version_warning = True

        if print_version_warning:
            click.echo(
                click.style(
                    f"Invalid choice. Defaulting to current Python version: {selected_version}",
                    fg="yellow",
                )
            )
        else:
            click.echo(
                click.style(
                    f"The selected Python [{selected_version}] version will be used for the project.",
                    fg="blue",
                )
            )

        return selected_version

    @staticmethod
    def _get_git_author_info() -> str:
        """
        Try to obtain author info from git config user.name and user.email.
        Return "Name <email>" if possible, otherwise return empty string.
        """
        try:
            name = subprocess.check_output(
                ["git", "config", "user.name"], text=True
            ).strip()
            email = subprocess.check_output(
                ["git", "config", "user.email"], text=True
            ).strip()
            if name and email:
                return f"{name} <{email}>"
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        return ""

    def _generate_pyproject_toml(
        self,
        project_name: str,
        morph_data_dependency: str,
    ) -> str:
        author = self._get_git_author_info()
        authors_line = f'authors = ["{author}"]\n' if author else ""

        return f"""[tool.poetry]
name = "{project_name}"
version = "0.1.0"
description = ""
{authors_line}readme = "README.md"
packages = [
    {{ include = "src" }}
]

[tool.poetry.dependencies]
python = ">=3.9,<3.13"
{morph_data_dependency}

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
"""

    def _generate_uv_pyproject_toml(
        self,
        project_name: str,
        morph_data_dependency: str,
    ) -> str:
        author = self._get_git_author_info()
        if author:
            match = re.match(r"(?P<name>[^<]+)\s*<(?P<email>[^>]+)>", author)
            if match:
                name = match.group("name").strip()
                email = match.group("email").strip()
                authors_line = f'authors = [{{ name = "{name}", email = "{email}" }}]\n'
            else:
                authors_line = f'authors = [{{ name = "{author}" }}]\n'
        else:
            authors_line = ""

        metadata_section = (
            "\n[tool.hatch.metadata]\nallow-direct-references = true\n"
            if self.is_development
            else ""
        )

        return f"""[project]
name = "{project_name}"
version = "0.1.0"
description = ""
{authors_line}readme = "README.md"
requires-python = ">=3.9,<3.13"
dependencies = [
    "{morph_data_dependency}"
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]
{metadata_section}"""
