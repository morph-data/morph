import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import click

from morph.cli.flags import Flags
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

        # Use the project directory name as the image name
        self.image_name = f"{os.path.basename(self.project_root)}:latest"

        # Output tar.gz file for the Docker image and dist directory
        self.output_tar_gz = os.path.join(
            self.project_root, "output", f"{os.path.basename(self.project_root)}.tar.gz"
        )

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
            click.echo(click.style("Docker daemon is running.", fg="green"))
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

        self.frontend_src_dir = os.path.join(
            Path(__file__).resolve().parents[1], "frontend"
        )
        self.frontend_dir = os.path.join(self.project_root, ".morph/frontend")
        self.dist_dir = os.path.join(self.frontend_dir, "dist")

    def run(self):
        """
        Entry point for running the morph deploy task.
        """
        click.echo(click.style("Starting DeployTask...", fg="green"))

        # Build the frontend, Docker image, and save to tar.gz
        self._build_frontend()
        self._build_docker_image()
        self._save_to_tar_gz()

        # TODO: Implement deployment sequence

        click.echo(click.style("DeployTask completed successfully!", fg="green"))

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

    def _save_to_tar_gz(self):
        """
        Save the Docker image and frontend dist directory to a tar.gz file.
        """
        try:
            output_dir = os.path.dirname(self.output_tar_gz)
            os.makedirs(output_dir, exist_ok=True)

            # Save the Docker image as a tar file
            docker_image_tar = os.path.join(output_dir, "docker_image.tar")
            click.echo(
                click.style(
                    f"Saving Docker image to '{docker_image_tar}'...", fg="blue"
                )
            )
            with open(docker_image_tar, "wb") as tar:
                subprocess.run(
                    ["docker", "save", self.image_name], stdout=tar, check=True
                )
            click.echo(
                click.style(f"Docker image saved to '{docker_image_tar}'.", fg="green")
            )

            # Create a tar.gz file containing the Docker image and dist directory
            click.echo(
                click.style(
                    f"Creating tar.gz archive '{self.output_tar_gz}'...", fg="blue"
                )
            )
            with tarfile.open(self.output_tar_gz, "w:gz") as tar:
                tar.add(docker_image_tar, arcname="docker_image.tar")
                tar.add(self.dist_dir, arcname="dist")
            click.echo(
                click.style(f"Archive created at '{self.output_tar_gz}'.", fg="green")
            )

            # Clean up temporary tar file
            os.remove(docker_image_tar)
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"Error saving Docker image: {str(e)}", fg="red"))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"Unexpected error: {str(e)}", fg="red"))
            sys.exit(1)
