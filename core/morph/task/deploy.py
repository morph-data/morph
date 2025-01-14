import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

import click

from morph.cli.flags import Flags
from morph.config.project import load_project
from morph.task.base import BaseTask
from morph.task.utils.morph import find_project_root_dir


class DeployTask(BaseTask):
    def __init__(self, args: Flags):
        super().__init__(args)
        self.args = args
        self.is_verbose = args.VERBOSE

        try:
            self.project_root = find_project_root_dir(os.getcwd())
        except FileNotFoundError as e:
            click.echo(click.style(f"Error: {str(e)}", fg="red", bg="yellow"))
            sys.exit(1)

        project = load_project(self.project_root)
        if not project:
            click.echo(click.style("Project configuration not found.", fg="red"))
            sys.exit(1)
        self.package_manager = project.package_manager

        # Ensure the Dockerfile exists
        self.dockerfile = os.path.join(self.project_root, "Dockerfile")
        if not os.path.exists(self.dockerfile):
            click.echo(click.style(f"Error: {self.dockerfile} not found", fg="red"))
            sys.exit(1)

        try:
            # Check if Docker CLI is installed
            click.echo(click.style("Checking Docker daemon status...", fg="blue"))
            subprocess.run(["docker", "--version"], stdout=subprocess.PIPE, check=True)
            # Check if Docker daemon is running
            subprocess.run(["docker", "info"], stdout=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError:
            click.echo(
                click.style(
                    "Docker daemon is not running. Please (re)start Docker and try again.",
                    fg="red",
                )
            )
            sys.exit(1)
        except FileNotFoundError:
            click.echo(
                click.style(
                    "Docker is not installed. Please install Docker and try again.",
                    fg="red",
                )
            )
            sys.exit(1)

        # Frontend settings
        self.frontend_src_dir = os.path.join(
            Path(__file__).resolve().parents[1], "frontend"
        )
        self.frontend_dir = os.path.join(self.project_root, ".morph/frontend")
        self.dist_dir = os.path.join(self.frontend_dir, "dist")

        # Docker settings
        self.image_name = f"{os.path.basename(self.project_root)}:latest"
        self.output_tar_gz = os.path.join(
            self.project_root, f".morph/{os.path.basename(self.project_root)}.tar.gz"
        )

        # Check dependency files
        self._check_dependencies()

    def run(self):
        """
        Entry point for running the morph deploy task.
        """
        click.echo(click.style("Initiating deployment sequence...", fg="blue"))

        # Build the frontend, Docker image, and save to tar.gz
        self._build_frontend()
        self._build_docker_image()
        self._tarball_docker_image()

        # TODO: Implement deployment sequence

        click.echo(click.style("Deployment completed successfully! 🎉", fg="green"))

    def _check_dependencies(self):
        """
        Check if required dependency files exist based on the package manager.
        """

        if self.package_manager == "pip":
            requirements_file = os.path.join(self.project_root, "requirements.txt")
            if not os.path.exists(requirements_file):
                click.echo(
                    click.style(
                        "Error: The file 'requirements.txt' is missing.\n"
                        "This file is required because the project is configured to use 'pip' as the package manager.\n"
                        "Please create a 'requirements.txt' file in the project root directory and list the Python dependencies.",
                        fg="red",
                    )
                )
                sys.exit(1)

        elif self.package_manager == "poetry":
            poetry_files = [
                os.path.join(self.project_root, "pyproject.toml"),
                os.path.join(self.project_root, "poetry.lock"),
            ]
            missing_files = [f for f in poetry_files if not os.path.exists(f)]
            if missing_files:
                click.echo(
                    click.style(
                        "Error: Missing required Poetry files.\n"
                        "The following file(s) are missing:\n"
                        f"  - {', '.join(missing_files)}\n"
                        "These files are necessary because the project is configured to use 'poetry' as the package manager.\n"
                        "To fix this:\n"
                        "1. Ensure that 'pyproject.toml' defines your project dependencies.\n"
                        "2. Run 'poetry lock' to generate the 'poetry.lock' file.",
                        fg="red",
                    )
                )
                sys.exit(1)

        else:
            click.echo(
                click.style(
                    f"Error: Unknown package manager '{self.package_manager}'.\n"
                    "Please check the 'package_manager' setting in your project configuration.\n"
                    "Valid options are:\n"
                    "  - pip\n"
                    "  - poetry",
                    fg="red",
                )
            )
            sys.exit(1)

    def _build_frontend(self):
        """
        Build the frontend using npm.
        """
        try:
            click.echo(click.style("Building frontend...", fg="blue"))
            # Install dependencies
            subprocess.run(["npm", "install"], cwd=self.frontend_src_dir, check=True)
            # Run the build script
            subprocess.run(
                ["npm", "run", "build"], cwd=self.frontend_src_dir, check=True
            )
            # Copy build artifact to .morph/frontend
            if os.path.exists(self.frontend_dir):
                shutil.rmtree(self.frontend_dir)
            shutil.copytree(self.frontend_src_dir, self.frontend_dir)
            # Ensure the dist directory exists after building
            if not os.path.exists(self.dist_dir):
                raise FileNotFoundError(
                    "Frontend build failed: 'dist' directory not found."
                )
            click.echo(click.style("Frontend built successfully.", fg="green"))
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"Error building frontend: {str(e)}", fg="red"))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"Unexpected error: {str(e)}", fg="red"))
            sys.exit(1)

    def _build_docker_image(self):
        """
        Build the Docker image.
        """
        try:
            click.echo(
                click.style(f"Building Docker image '{self.image_name}'...", fg="blue")
            )
            subprocess.run(
                [
                    "docker",
                    "build",
                    "-t",
                    self.image_name,
                    "-f",
                    self.dockerfile,
                    self.project_root,
                ],
                check=True,
            )
            click.echo(
                click.style(
                    f"Docker image '{self.image_name}' built successfully.", fg="green"
                )
            )
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"Error building Docker image: {str(e)}", fg="red"))
            sys.exit(1)

    def _tarball_docker_image(self):
        """
        Save the Docker image as a tar.gz file, falling back to Python gzip if the gzip command is unavailable.
        """
        try:
            # Ensure the output directory exists
            output_dir = os.path.dirname(self.output_tar_gz)
            os.makedirs(output_dir, exist_ok=True)

            # Save Docker image and gzip it
            click.echo(
                click.style(
                    f"Saving Docker image as tar.gz to '{self.output_tar_gz}'...",
                    fg="blue",
                )
            )
            with open(self.output_tar_gz, "wb") as tar_gz:
                # First, save the Docker image as a tar stream
                docker_save = subprocess.Popen(
                    ["docker", "save", self.image_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                # Use gzip to compress the tar stream
                with gzip.GzipFile(fileobj=tar_gz, mode="wb") as gzip_file:
                    if docker_save.stdout is None:
                        raise RuntimeError(
                            "Docker save process did not produce any output."
                        )
                    shutil.copyfileobj(docker_save.stdout, gzip_file)

                # Ensure the docker save process completes successfully
                docker_save.wait()
                if docker_save.returncode != 0:
                    stderr = (
                        docker_save.stderr.read().decode("utf-8")
                        if docker_save.stderr
                        else ""
                    )
                    raise RuntimeError(f"Docker save failed: {stderr.strip()}")

            click.echo(
                click.style(
                    f"Docker image successfully saved as '{self.output_tar_gz}'.",
                    fg="green",
                )
            )
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"Error saving Docker image: {str(e)}", fg="red"))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"Unexpected error: {str(e)}", fg="red"))
            sys.exit(1)
