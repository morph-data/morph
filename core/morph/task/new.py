import importlib.metadata
import os
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
            "1": "pip",
            "2": "poetry",
        }
        click.echo()
        click.echo("Select a package manager for your project:")
        for key, value in package_manager_options.items():
            click.echo(click.style(f"{key}: {value}", fg="blue"))

        click.echo(
            click.style("Enter the number of your choice. (default is ["), nl=False
        )
        click.echo(click.style("1: pip", fg="blue"), nl=False)
        click.echo(click.style("]): "), nl=False)
        package_manager_choice = input().strip()

        # Validate user input and set the package manager
        project.package_manager = package_manager_options.get(
            package_manager_choice, "pip"
        )
        if project.package_manager not in package_manager_options.values():
            click.echo(
                click.style(
                    "Warning: Invalid package manager. Defaulting to 'pip'.",
                    fg="yellow",
                )
            )
            project.package_manager = "pip"

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
                    dependency = f"git+https://github.com/morph-data/morph.git@{branch}"
                else:
                    dependency = (
                        f"morph-data=={morph_data_version}"
                        if morph_data_version
                        else "morph-data"
                    )

                # Use poetry init with the --dependency option
                subprocess.run(
                    ["poetry", "init", "--no-interaction", "--dependency", dependency],
                    check=True,
                )

                click.echo(
                    click.style(
                        f"Added 'morph-data' to pyproject.toml with {dependency}.",
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
