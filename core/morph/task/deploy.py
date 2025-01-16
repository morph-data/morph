import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

import click
import requests
from tqdm import tqdm

from morph.api.cloud.client import MorphApiKeyClientImpl
from morph.api.cloud.types import EnvVarObject
from morph.cli.flags import Flags
from morph.config.project import load_project
from morph.task.base import BaseTask
from morph.task.utils.file_upload import FileWithProgress
from morph.task.utils.morph import find_project_root_dir


class DeployTask(BaseTask):
    def __init__(self, args: Flags):
        super().__init__(args)
        self.args = args
        self.no_cache = args.NO_CACHE
        self.is_verbose = args.VERBOSE

        # Attempt to find the project root
        try:
            self.project_root = find_project_root_dir(os.getcwd())
        except FileNotFoundError as e:
            click.echo(click.style(f"Error: {str(e)}", fg="red"))
            sys.exit(1)

        # Load morph_project.yml or equivalent
        project = load_project(self.project_root)
        if not project:
            click.echo(click.style("Project configuration not found.", fg="red"))
            sys.exit(1)
        self.package_manager = project.package_manager

        # Check Dockerfile existence
        self.dockerfile = os.path.join(self.project_root, "Dockerfile")
        if not os.path.exists(self.dockerfile):
            click.echo(click.style(f"Error: {self.dockerfile} not found", fg="red"))
            sys.exit(1)

        # Check Docker availability
        try:
            click.echo(click.style("Checking Docker daemon status...", fg="blue"))
            subprocess.run(["docker", "--version"], stdout=subprocess.PIPE, check=True)
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
        self.frontend_dir = os.path.join(self.project_root, ".morph/frontend")
        self.dist_dir = os.path.join(self.frontend_dir, "dist")

        # Docker image settings: use .tar instead
        self.image_name = f"{os.path.basename(self.project_root)}:latest"
        self.output_tar = os.path.join(
            self.project_root, f".morph/{os.path.basename(self.project_root)}.tar"
        )

        # Verify dependencies
        self._verify_dependencies()

        # Initialize the Morph API client
        try:
            self.client = MorphApiKeyClientImpl()
        except ValueError as e:
            click.echo(click.style(f"Error: {str(e)}", fg="red"))
            sys.exit(1)

        # Verify environment variables
        self.env_file = os.path.join(self.project_root, ".env")
        if os.path.exists(self.env_file):
            self._verify_environment_variables()

    def run(self):
        """
        Main entry point for the morph deploy task.
        """
        click.echo(click.style("Initiating deployment sequence...", fg="blue"))

        # Copy app.py (entrypoint for lambda) to .morph directory
        api_dir = Path(__file__).parents[1].joinpath("api")
        entrypoint_file = api_dir.joinpath("app.py")
        if not entrypoint_file.exists():
            click.echo(
                click.style(f"Entrypoint file not found: {entrypoint_file}", fg="red")
            )
            sys.exit(1)
        shutil.copy2(entrypoint_file, os.path.join(self.project_root, ".morph/app.py"))

        # 1. Build the frontend
        self._build_frontend()

        # 2. Build the Docker image
        click.echo(click.style("Building Docker image...", fg="blue"))
        self._build_docker_image()

        # 3. Save Docker image as .tar
        click.echo(click.style("Saving Docker image as .tar...", fg="blue"))
        self._save_docker_image()

        # 4. Compute the checksum of the .tar file
        image_checksum = self._get_image_digest(self.image_name)
        click.echo(click.style(f"Docker image checksum: {image_checksum}", fg="blue"))

        # 5. Call the Morph API to initialize a deployment and get the pre-signed URL
        try:
            initialize_resp = self.client.initiate_deployment(
                project_id=self.client.project_id,
                image_build_log="",  # TODO: capture Docker build logs
                image_checksum=image_checksum,
            )
        except Exception as e:
            click.echo(
                click.style(f"Error initializing deployment: {str(e)}", fg="red")
            )
            sys.exit(1)

        if initialize_resp.is_error():
            click.echo(
                click.style(
                    f"Error initializing deployment: {initialize_resp.text}",
                    fg="red",
                )
            )
            sys.exit(1)

        presigned_url = initialize_resp.json().get("imageLocation")
        if not presigned_url:
            click.echo(
                click.style("Error: No 'imageLocation' in the response.", fg="red")
            )
            sys.exit(1)

        user_function_deployment_id = initialize_resp.json().get(
            "userFunctionDeploymentId"
        )
        if not user_function_deployment_id:
            click.echo(
                click.style(
                    "Error: No 'userFunctionDeploymentId' in the response.", fg="red"
                )
            )
            sys.exit(1)

        # 6. Upload the tar to the pre-signed URL
        self._upload_image_to_presigned_url(presigned_url, self.output_tar)

        # 7. Execute the deployment
        try:
            execute_resp = self.client.execute_deployment(user_function_deployment_id)
        except Exception as e:
            click.echo(click.style(f"Error executing deployment: {str(e)}", fg="red"))
            sys.exit(1)

        if execute_resp.is_error():
            click.echo(
                click.style(
                    f"Error executing deployment: {execute_resp.text}",
                    fg="red",
                )
            )
            sys.exit(1)

        status = execute_resp.json().get("status")
        if not status:
            click.echo(click.style("Error: No 'status' in the response.", fg="red"))
            sys.exit(1)

        click.echo(click.style(f"Deployment status: {status}", fg="blue"))

        # 8. Override environment variables
        self._override_env_variables()

        click.echo(click.style("Deployment completed successfully! 🎉", fg="green"))

    # --------------------------------------------------------
    # Internal methods
    # --------------------------------------------------------
    def _verify_dependencies(self) -> None:
        """
        Checks if the required dependency files exist based on the package manager.
        """
        if self.package_manager == "pip":
            requirements_file = os.path.join(self.project_root, "requirements.txt")
            if not os.path.exists(requirements_file):
                click.echo(
                    click.style(
                        "Error: 'requirements.txt' is missing. Please create it.",
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
                        f"Error: Missing Poetry files: {missing_files}",
                        fg="red",
                    )
                )
                sys.exit(1)
        else:
            click.echo(
                click.style(
                    f"Error: Unknown package manager '{self.package_manager}'.",
                    fg="red",
                )
            )
            sys.exit(1)

    def _verify_environment_variables(self) -> None:
        # Check environment variables in the Morph Cloud
        try:
            env_vars_resp = self.client.list_env_vars()
        except Exception as e:
            click.echo(
                click.style(f"Error fetching environment variables: {str(e)}", fg="red")
            )
            sys.exit(1)

        if env_vars_resp.is_error():
            click.echo(
                click.style(
                    f"Error fetching environment variables: {env_vars_resp.text}",
                    fg="red",
                )
            )
            sys.exit(1)

        items = env_vars_resp.json().get("items")
        if not items:
            return

        # TODO: Remove debug print
        print("==================== FOR DEBUGGING ====================")
        print(items)

        click.echo(
            click.style(
                "Warning: .env file detected! This command will override environment variables in the Morph Cloud with local .env file.",
                fg="yellow",
            )
        )
        if (
            input(
                "Are you sure you want to continue? (Y/n): ",
            )
            != "Y"
        ):
            click.echo(click.style("Aborted!"))
            sys.exit(1)

    def _build_frontend(self):
        """
        Builds the frontend using npm and moves the build output into .morph/frontend.
        """
        try:
            click.echo(click.style("Building frontend...", fg="blue"))

            # Run npm install and build
            subprocess.run(["npm", "install"], cwd=self.project_root, check=True)
            subprocess.run(["npm", "run", "build"], cwd=self.project_root, check=True)

            dist_dir = os.path.join(self.project_root, "dist")
            if not os.path.exists(dist_dir):
                raise FileNotFoundError(
                    "Frontend build failed: 'dist/' directory not found."
                )

            # Remove existing .morph/frontend if it exists
            if os.path.exists(self.frontend_dir):
                shutil.rmtree(self.frontend_dir)  # Remove existing frontend directory
            os.makedirs(self.frontend_dir, exist_ok=True)

            # Move dist/ to .morph/frontend
            shutil.move(dist_dir, self.dist_dir)

        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"Error building frontend: {str(e)}", fg="red"))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"Unexpected error: {str(e)}", fg="red"))
            sys.exit(1)

    def _build_docker_image(self):
        """
        Builds the Docker image using the local Dockerfile.
        """
        try:
            docker_build_cmd = [
                "docker",
                "build",
                "-t",
                self.image_name,
                "-f",
                self.dockerfile,
                self.project_root,
            ]
            if self.no_cache:
                docker_build_cmd.append("--no-cache")
            subprocess.run(docker_build_cmd, check=True)
            click.echo(
                click.style(
                    f"Docker image '{self.image_name}' built successfully.", fg="green"
                )
            )
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"Error building Docker image: {str(e)}", fg="red"))
            sys.exit(1)

    def _save_docker_image(self):
        """
        Saves the Docker image as a .tar file without compression.
        """
        try:
            output_dir = os.path.dirname(self.output_tar)
            os.makedirs(output_dir, exist_ok=True)

            if os.path.exists(self.output_tar):
                os.remove(self.output_tar)  # remove any existing file

            # Docker save command with -o option
            subprocess.run(
                ["docker", "save", "-o", self.output_tar, self.image_name],
                check=True,
            )
            if not os.path.exists(self.output_tar):
                raise FileNotFoundError("Docker save failed to produce the .tar file.")

            file_size_mb = os.path.getsize(self.output_tar) / (1024 * 1024)
            click.echo(
                click.style(
                    f"Docker image saved as '{self.output_tar}' ({file_size_mb:.2f} MB).",
                    fg="blue",
                )
            )
        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"Error saving Docker image: {str(e)}", fg="red"))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"Unexpected error: {str(e)}", fg="red"))
            sys.exit(1)

    @staticmethod
    def _get_image_digest(image_name: str) -> str:
        """
        Retrieves the sha256 digest of the specified Docker image.
        @param image_name:
        @return:
        """
        try:
            # Use `docker inspect` to get the image digest
            result = subprocess.run(
                ["docker", "inspect", "--format='{{index .Id}}'", image_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
            digest = result.stdout.strip().strip("'")
            if digest.startswith("sha256:"):
                return digest
            else:
                raise ValueError(f"Unexpected digest format: {digest}")
        except subprocess.CalledProcessError as e:
            click.echo(
                click.style(f"Error retrieving Docker image digest: {str(e)}", fg="red")
            )
            sys.exit(1)
        except Exception as e:
            click.echo(
                click.style(
                    f"Unexpected error retrieving Docker image digest: {str(e)}",
                    fg="red",
                )
            )
            sys.exit(1)

    @staticmethod
    def _upload_image_to_presigned_url(presigned_url: str, file_path: str) -> None:
        """
        Uploads the specified file to the S3 presigned URL.
        @param presigned_url:
        @param file_path:
        @return:
        """
        file_size = os.path.getsize(file_path)
        click.echo(
            click.style(
                f"Uploading .tar image ({file_size / (1024 * 1024):.2f} MB) to the presigned URL...",
                fg="blue",
            )
        )

        with tqdm(total=file_size, unit="B", unit_scale=True, desc="Uploading") as pbar:
            with FileWithProgress(file_path, pbar) as fwp:
                headers = {
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(file_size),
                }
                response = requests.put(
                    presigned_url,
                    data=fwp,
                    headers=headers,
                )

        if not (200 <= response.status_code < 300):
            click.echo(
                click.style(
                    f"Failed to upload image. Status code: {response.status_code}, Response: {response.text}",
                    fg="red",
                )
            )
            sys.exit(1)

        click.echo(click.style("Upload completed successfully.", fg="green"))

    def _override_env_variables(self) -> None:
        """
        Overrides the environment variables in the Morph Cloud with the local .env file.
        @param self:
        @return:
        """
        env_vars: List[EnvVarObject] = []
        with open(self.env_file, "r") as f:
            for line in f:
                if not line.strip() or line.startswith("#"):
                    continue
                key, value = line.strip().split("=", 1)
                env_vars.append(EnvVarObject(key=key, value=value))

        try:
            override_res = self.client.override_env_vars(env_vars=env_vars)
        except Exception as e:
            click.echo("")
            click.echo(
                click.style(
                    f"Error overriding environment variables: {str(e)}", fg="red"
                )
            )
            sys.exit(1)

        if override_res.is_error():
            click.echo("")
            click.echo(
                click.style(
                    f"Waring: Failed to override environment variables. {override_res.reason}",
                    fg="yellow",
                )
            )
        else:
            click.echo(click.style(" done!", fg="green"))
