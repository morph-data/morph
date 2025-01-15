# deploy.py
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import click
import requests
from tqdm import tqdm

from morph.api.cloud.client import MorphApiKeyClientImpl
from morph.cli.flags import Flags
from morph.config.project import load_project
from morph.task.base import BaseTask
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
        self.frontend_src_dir = os.path.join(
            Path(__file__).resolve().parents[1], "frontend"
        )
        self.frontend_dir = os.path.join(self.project_root, ".morph/frontend")
        self.dist_dir = os.path.join(self.frontend_dir, "dist")

        # Docker image settings: use .tar instead
        self.image_name = f"{os.path.basename(self.project_root)}:latest"
        self.output_tar = os.path.join(
            self.project_root, f".morph/{os.path.basename(self.project_root)}.tar"
        )

        # Verify dependencies
        self._verify_dependencies()

    def run(self):
        """
        Main entry point for the morph deploy task.
        """
        click.echo(click.style("Initiating deployment sequence...", fg="blue"))

        # Copy main.py (entrypoint for lambda) to .morph directory
        template_dir = Path(__file__).parents[1].joinpath("include")
        entrypoint_file = template_dir.joinpath("main.py")
        if not entrypoint_file.exists():
            click.echo(
                click.style(f"Entrypoint file not found: {entrypoint_file}", fg="red")
            )
            sys.exit(1)
        shutil.copy2(entrypoint_file, os.path.join(self.project_root, ".morph/main.py"))

        # 1. Build the frontend
        self._build_frontend()

        # 2. Build the Docker image
        click.echo(click.style("Building Docker image...", fg="blue"))
        self._build_docker_image()

        # 3. Save Docker image as .tar
        click.echo(click.style("Saving Docker image as .tar...", fg="blue"))
        self._save_docker_image()

        # 4. Compute the checksum of the .tar file
        image_checksum = self._compute_file_sha256(self.output_tar)
        click.echo(click.style(f"Computed checksum: {image_checksum}", fg="blue"))

        # 5. Call the Morph API to create a deployment and get the pre-signed URL
        try:
            client = MorphApiKeyClientImpl()
        except ValueError as e:
            click.echo(click.style(f"Error: {str(e)}", fg="red"))
            sys.exit(1)
        create_resp = client.create_deployment(
            project_id=client.project_id,
            image_build_log="(Optional) Docker build logs here",
            image_checksum=image_checksum,
        )

        # Extract presigned URL and deployment ID from the response
        presigned_url = create_resp.data.get("imageLocation")
        if not presigned_url:
            click.echo(
                click.style("Error: No 'imageLocation' in the response.", fg="red")
            )
            sys.exit(1)

        user_function_deployment_id = create_resp.data.get("userFunctionDeploymentId")
        if not user_function_deployment_id:
            click.echo(
                click.style(
                    "Error: No 'userFunctionDeploymentId' in the response.", fg="red"
                )
            )
            sys.exit(1)

        # 6. Upload the tar to the pre-signed URL
        self._upload_image_to_presigned_url(presigned_url, self.output_tar)

        # 7. Finalize the deployment
        finalize_resp = client.finalize_deployment(user_function_deployment_id)
        status = finalize_resp.data.get("status", "UNKNOWN")
        click.echo(click.style(f"Deployment status: {status}", fg="blue"))

        click.echo(click.style("Deployment completed successfully! 🎉", fg="green"))

    # --------------------------------------------------------
    # Internal methods
    # --------------------------------------------------------
    def _verify_dependencies(self):
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

    def _build_frontend(self):
        """
        Builds the frontend using npm.
        """
        try:
            click.echo(click.style("Building frontend...", fg="blue"))
            subprocess.run(["npm", "install"], cwd=self.frontend_src_dir, check=True)
            subprocess.run(
                ["npm", "run", "build"], cwd=self.frontend_src_dir, check=True
            )

            if os.path.exists(self.frontend_dir):
                shutil.rmtree(self.frontend_dir)
            shutil.copytree(self.frontend_src_dir, self.frontend_dir)

            if not os.path.exists(self.dist_dir):
                raise FileNotFoundError(
                    "Frontend build failed: no 'dist' directory found."
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
    def _compute_file_sha256(file_path: str) -> str:
        """
        Computes and returns the SHA256 checksum of the specified file.
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @staticmethod
    def _upload_image_to_presigned_url(presigned_url: str, file_path: str):
        """
        Uploads the local .tar image to the specified pre-signed URL via PUT.
        Uses a progress bar to show upload progress.
        """
        file_size = os.path.getsize(file_path)
        click.echo(
            click.style("Uploading .tar image to the presigned URL...", fg="blue")
        )

        with open(file_path, "rb") as f, tqdm(
            total=file_size,
            unit="B",
            unit_scale=True,
            desc="Uploading",
        ) as pbar:
            response = requests.put(
                presigned_url,
                data=f,
                headers={"Content-Type": "application/octet-stream"},
            )
            pbar.update(file_size)

        if response.status_code not in (200, 201):
            click.echo(
                click.style(
                    f"Failed to upload image. Status code: {response.status_code}, Response: {response.text}",
                    fg="red",
                )
            )
            sys.exit(1)

        click.echo(click.style("Upload completed successfully.", fg="green"))
