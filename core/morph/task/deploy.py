import os
import pty
import re
import select
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

import click
import requests
from tqdm import tqdm

from morph.api.cloud.client import MorphApiKeyClientImpl
from morph.api.cloud.types import EnvVarObject
from morph.cli.flags import Flags
from morph.config.project import load_project
from morph.task.base import BaseTask
from morph.task.utils.file_upload import FileWithProgress
from morph.task.utils.morph import find_project_root_dir, initialize_frontend_dir


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
        elif project.project_id is None:
            click.echo(
                click.style(
                    "Error: No project id found. Please fill project_id in morph_project.yml.",
                    fg="red",
                )
            )
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

        # Initialize the Morph API client
        try:
            self.client = MorphApiKeyClientImpl()
        except ValueError as e:
            click.echo(click.style(f"Error: {str(e)}", fg="red"))
            sys.exit(1)

        # Frontend and backend settings
        self.frontend_dir = initialize_frontend_dir(self.project_root)
        self.backend_template_dir = os.path.join(Path(__file__).resolve().parents[2])
        self.backend_dir = os.path.join(self.project_root, ".morph/core")

        # Docker settings
        self.image_name = f"{os.path.basename(self.project_root)}:latest"
        self.output_tar = os.path.join(
            self.project_root, f".morph/{os.path.basename(self.project_root)}.tar"
        )

        # Verify dependencies
        self._verify_dependencies()

        # Verify environment variables
        self.env_file = os.path.join(self.project_root, ".env")
        self.should_override_env = False
        if os.path.exists(self.env_file):
            self.should_override_env = self._verify_environment_variables()

        # Validate API key
        self._validate_api_key()

    def run(self):
        """
        Main entry point for the morph deploy task.
        """
        click.echo(click.style("Initiating deployment sequence...", fg="blue"))

        # 1. Build the source code
        self._copy_and_build_source()

        # 2. Build the Docker image
        click.echo(click.style("Building Docker image...", fg="blue"))
        image_build_log = self._build_docker_image()

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
                image_build_log=image_build_log,
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

        # 7. Override environment variables
        if self.should_override_env:
            self._override_env_variables()

        # 8. Execute deployment and monitor status
        self._execute_deployment(user_function_deployment_id)

        click.echo(click.style("Deployment completed successfully! 🎉", fg="green"))

    # --------------------------------------------------------
    # Internal methods
    # --------------------------------------------------------
    def _verify_dependencies(self) -> None:
        """
        Checks if the required dependency files exist based on the package manager
        and ensures 'morph-data' is included in the dependencies.
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

            # Check if 'morph-data' is listed in requirements.txt
            with open(requirements_file, "r") as f:
                requirements = f.read()
            if "morph-data" not in requirements:
                click.echo(
                    click.style(
                        "Error: 'morph-data' is not listed in 'requirements.txt'. Please add it.",
                        fg="red",
                    )
                )
                sys.exit(1)
        elif self.package_manager == "poetry":
            pyproject_file = os.path.join(self.project_root, "pyproject.toml")
            requirements_file = os.path.join(self.project_root, "requirements.txt")

            missing_files = [f for f in [pyproject_file] if not os.path.exists(f)]
            if missing_files:
                click.echo(
                    click.style(
                        f"Error: Missing Poetry files: {missing_files}",
                        fg="red",
                    )
                )
                sys.exit(1)

            # Check if 'morph-data' is listed in pyproject.toml
            with open(pyproject_file, "r") as f:
                pyproject_content = f.read()
            if "morph-data" not in pyproject_content:
                click.echo(
                    click.style(
                        "Error: 'morph-data' is not listed in 'pyproject.toml'. Please add it.",
                        fg="red",
                    )
                )
                sys.exit(1)
            # Generate requirements.txt using poetry export
            click.echo(
                click.style(
                    "Exporting requirements.txt from Poetry environment...", fg="blue"
                )
            )
            try:
                subprocess.run(
                    [
                        "poetry",
                        "export",
                        "-f",
                        "requirements.txt",
                        "-o",
                        requirements_file,
                        "--without-hashes",
                    ],
                    check=True,
                )
                click.echo(
                    click.style(
                        f"'requirements.txt' generated successfully at: {requirements_file}",
                        fg="green",
                    )
                )
            except subprocess.CalledProcessError as e:
                click.echo(
                    click.style(f"Error exporting requirements.txt: {str(e)}", fg="red")
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

    def _verify_environment_variables(self) -> bool:
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
            # No environment variables in the Morph Cloud
            # In this case, there is no need to warn the user
            return True

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

        return True

    def _validate_api_key(self):
        res = self.client.check_api_secret()
        if res.is_error():
            click.echo(
                click.style(
                    "Error: API key is invalid.",
                    fg="red",
                )
            )
            sys.exit(1)

    def _copy_and_build_source(self):
        click.echo(click.style("Building frontend...", fg="blue"))
        try:
            # Run npm install and build
            subprocess.run(["npm", "install"], cwd=self.project_root, check=True)
            subprocess.run(["npm", "run", "build"], cwd=self.project_root, check=True)

        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"Error building frontend: {str(e)}", fg="red"))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"Unexpected error: {str(e)}", fg="red"))
            sys.exit(1)

        click.echo(click.style("Building backend...", fg="blue"))
        try:
            # Copy the backend template
            if os.path.exists(self.backend_dir):
                shutil.rmtree(self.backend_dir)  # Remove existing backend directory
            os.makedirs(self.backend_dir, exist_ok=True)
            shutil.copytree(
                self.backend_template_dir, self.backend_dir, dirs_exist_ok=True
            )

            # Compile the morph project
            subprocess.run(
                ["morph", "compile", "--force"], cwd=self.project_root, check=True
            )

        except subprocess.CalledProcessError as e:
            click.echo(click.style(f"Error building backend: {str(e)}", fg="red"))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"Unexpected error: {str(e)}", fg="red"))
            sys.exit(1)

    def _build_docker_image(self) -> str:
        """
        Builds the Docker image using a pseudo-terminal (PTY) to preserve colored output.
        Captures logs in plain text format (with ANSI codes removed) for cloud storage while
        adding color to local terminal output for better readability.
        """
        try:
            docker_build_cmd = [
                "docker",
                "build",
                "--progress=plain",
                # Simplifies logs by avoiding line overwrites in cloud logs; removes colors and animations
                "-t",
                self.image_name,
                "-f",
                self.dockerfile,
                self.project_root,
            ]
            if self.no_cache:
                docker_build_cmd.append("--no-cache")

            # Regex to strip ANSI escape sequences for storing logs as plain text
            ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

            # Create a pseudo-terminal pair
            master_fd, slave_fd = pty.openpty()

            # Spawn the Docker build process with PTY
            process = subprocess.Popen(
                docker_build_cmd,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                text=False,  # Receive raw binary data (not decoded text)
                bufsize=0,  # No extra buffering
            )

            # The slave FD is not needed after starting the process
            os.close(slave_fd)

            build_logs = []

            while True:
                # Use select to check if there's data to read from the master FD
                r, _, _ = select.select([master_fd], [], [], 0.1)
                if master_fd in r:
                    # Read up to 1KB from the master FD
                    try:
                        chunk = os.read(master_fd, 1024)
                    except OSError:
                        # If reading fails, exit the loop
                        break

                    if not chunk:
                        # EOF
                        break

                    # Remove ANSI codes and store logs for cloud storage
                    text_chunk = chunk.decode(errors="replace")
                    clean_text = ansi_escape.sub("", text_chunk)
                    build_logs.append(clean_text)

                    # Add color to logs for local terminal
                    colored_chunk = click.style(clean_text, fg="blue")
                    sys.stdout.write(colored_chunk)
                    sys.stdout.flush()

                # If the process has exited, read any remaining data
                if process.poll() is not None:
                    # Read everything left until EOF
                    while True:
                        try:
                            chunk = os.read(master_fd, 1024)
                            if not chunk:
                                break
                            text_chunk = chunk.decode(errors="replace")
                            clean_text = ansi_escape.sub("", text_chunk)
                            build_logs.append(clean_text)
                            colored_chunk = click.style(clean_text, fg="blue")
                            sys.stdout.write(colored_chunk)
                            sys.stdout.flush()
                        except OSError:
                            break
                    break

            # Close the master FD
            os.close(master_fd)

            return_code = process.wait()
            if return_code != 0:
                # If Docker build failed, show the full logs and raise an error
                all_logs = "".join(build_logs)
                raise subprocess.CalledProcessError(
                    return_code, docker_build_cmd, output=all_logs
                )

            click.echo(
                click.style(
                    f"Docker image '{self.image_name}' built successfully.", fg="green"
                )
            )
            # Return the captured logs as plain text
            return "".join(build_logs)

        except subprocess.CalledProcessError:
            click.echo(
                click.style(
                    f"Error building Docker image '{self.image_name}'.", fg="red"
                )
            )
            sys.exit(1)
        except Exception as e:
            click.echo(
                click.style(
                    f"Unexpected error while building Docker image: {str(e)}", fg="red"
                )
            )
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
        click.echo(
            click.style("Overriding Morph cloud environment variables...", fg="blue"),
            nl=False,
        )

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

    def _execute_deployment(
        self,
        user_function_deployment_id: str,
        timeout: int = 900,
        enable_status_polling: Optional[bool] = False,
    ) -> None:
        """
        Executes the deployment and monitors its status until completion.

        Args:
            user_function_deployment_id (str): The deployment ID to monitor.
            timeout (int): Maximum time to wait for status change (in seconds). Default is 15 minutes.
            enable_status_polling (bool): Enable status polling. Default is False.
        """
        start_time = time.time()
        interval = 5  # Initial polling interval in seconds

        click.echo(
            click.style(
                f"Deployment started. (user_function_deployment_id: {user_function_deployment_id})",
                fg="blue",
            )
        )

        # Initial API call to execute deployment
        try:
            execute_resp = self.client.execute_deployment(user_function_deployment_id)
            if execute_resp.is_error():
                click.echo(
                    click.style(
                        f"Error executing deployment: {execute_resp.text}", fg="red"
                    )
                )
                sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"Error executing deployment: {str(e)}", fg="red"))
            sys.exit(1)

        if not enable_status_polling:
            status = execute_resp.json().get("status")
            if status == "succeeded":
                return

        click.echo(
            click.style(
                "Monitoring deployment status...",
                fg="blue",
            ),
            nl=False,
        )

        # Monitor the deployment status
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout:
                click.echo("")
                click.echo(
                    click.style(
                        "Timeout: Deployment did not finish within the allotted time.",
                        fg="red",
                    )
                )
                sys.exit(1)

            try:
                # Fetch deployment status
                status_resp = self.client.execute_deployment(
                    user_function_deployment_id
                )
                if status_resp.is_error():
                    click.echo("")
                    click.echo(
                        click.style(
                            f"Error fetching deployment status: {status_resp.text}",
                            fg="red",
                        )
                    )
                    sys.exit(1)

                status = status_resp.json().get("status")
                if not status:
                    click.echo("")
                    click.echo(
                        click.style("Error: No 'status' in the response.", fg="red")
                    )
                    sys.exit(1)

                # Check for final states
                if status in ["succeeded", "failed"]:
                    if status == "succeeded":
                        click.echo(click.style(" done!", fg="green"))
                        return
                    else:
                        click.echo("")
                        click.echo(
                            click.style(
                                f"Deployment failed: {status_resp.json().get('message')}",
                                fg="red",
                            )
                        )
                        sys.exit(1)

            except Exception as e:
                click.echo("")
                click.echo(
                    click.style(f"Error fetching deployment status: {str(e)}", fg="red")
                )
                sys.exit(1)

            # Adjust polling interval dynamically
            if elapsed_time < 300:  # First 5 minutes
                interval = 5
            elif elapsed_time < 600:  # Next 5 minutes
                interval = 15
            else:  # Beyond 10 minutes
                interval = 30

            time.sleep(interval)
