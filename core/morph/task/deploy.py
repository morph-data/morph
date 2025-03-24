import os
import re
import select
import subprocess
import sys
import time
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
from morph.task.utils.load_dockerfile import get_dockerfile_from_api
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
        self.project = load_project(self.project_root)
        if not self.project:
            click.echo(click.style("Project configuration not found.", fg="red"))
            sys.exit(1)
        elif self.project.project_id is None:
            click.echo(
                click.style(
                    "Error: No project id found. Please fill project_id in morph_project.yml.",
                    fg="red",
                )
            )
            sys.exit(1)
        self.package_manager = self.project.package_manager

        # Check Dockerfile existence
        self.dockerfile_path = os.path.join(self.project_root, "Dockerfile")
        self.use_custom_dockerfile = os.path.exists(self.dockerfile_path)
        if self.use_custom_dockerfile:
            provider = "aws"
            if (
                self.project.deployment is not None
                and self.project.deployment.provider is not None
            ):
                provider = self.project.deployment.provider or "aws"
            if self.project.build is None:
                dockerfile, dockerignore = get_dockerfile_from_api(
                    "morph", provider, None, None
                )
            else:
                dockerfile, dockerignore = get_dockerfile_from_api(
                    self.project.build.framework or "morph",
                    provider,
                    self.project.build.package_manager,
                    self.project.build.runtime,
                )
            with open(self.dockerfile_path, "w") as f:
                f.write(dockerfile)
            dockerignore_path = os.path.join(self.project_root, ".dockerignore")
            with open(dockerignore_path, "w") as f:
                f.write(dockerignore)

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

        # Docker settings
        self.image_name = f"{os.path.basename(self.project_root)}:latest"
        self.output_tar = os.path.join(
            self.project_root, f".morph/{os.path.basename(self.project_root)}.tar"
        )

        # Verify dependencies
        self._verify_dependencies()

        # Verify environment variables
        self.env_file = os.path.join(self.project_root, ".env")
        self.should_override_env = self._verify_environment_variables()

        # Validate API key
        self._validate_api_key()

    def run(self):
        """
        Main entry point for the morph deploy task.
        """
        click.echo(click.style("Initiating deployment sequence...", fg="blue"))

        # 1. Build the source code
        self._build_source()

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
                config=self.project.model_dump() if self.project else None,
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
        elif self.package_manager == "uv":
            uv_project_file = os.path.join(self.project_root, "pyproject.toml")
            requirements_file = os.path.join(self.project_root, "requirements.txt")

            missing_files = [f for f in [uv_project_file] if not os.path.exists(f)]
            if missing_files:
                click.echo(
                    click.style(
                        f"Error: Missing uv configuration files: {missing_files}",
                        fg="red",
                    )
                )
                sys.exit(1)

            # Check if 'morph-data' is listed in pyproject.yoml
            with open(uv_project_file, "r") as f:
                uv_project_content = f.read()
            if "morph-data" not in uv_project_content:
                click.echo(
                    click.style(
                        "Error: 'morph-data' is not listed in 'pyproject.toml'. Please add it.",
                        fg="red",
                    )
                )
                sys.exit(1)

            # Generate requirements.txt using uv export
            click.echo(
                click.style(
                    "Exporting requirements.txt from uv environment...", fg="blue"
                )
            )
            try:
                subprocess.run(
                    [
                        "uv",
                        "pip",
                        "compile",
                        "pyproject.toml",
                        "-o",
                        requirements_file,
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
        # Nothing to do if .env file does not exist
        if not os.path.exists(self.env_file):
            return False

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

        # Request user input to decide whether to override environment variables
        click.echo(click.style("Detected a local .env file!", fg="yellow"))
        click.echo(click.style("Choose how to proceed:", fg="blue"))
        click.echo(
            click.style("  1) Deploy without using .env (No override)", fg="blue")
        )
        click.echo(
            click.style(
                "  2) Use .env to override environment variables in Morph Cloud",
                fg="blue",
            )
        )
        choice = input("Select (1 or 2) [default: 1]: ")

        if not choice or choice == "1":
            click.echo(click.style("Defaulting to not overriding.", fg="yellow"))
            return False
        elif choice == "2":
            click.echo(
                click.style(
                    "Proceeding with environment variable override.", fg="green"
                )
            )
            return True
        else:
            click.echo(
                click.style(
                    "Invalid choice. Defaulting to not overriding.", fg="yellow"
                )
            )
            return False

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

    def _build_source(self):
        click.echo(click.style("Compiling morph project...", fg="blue"))
        try:
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
        Builds the Docker image using a pseudo-terminal (PTY) to preserve colored output on Unix-like systems.
        On Windows, termios/pty is not available, so we fall back to a simpler subprocess approach.
        """
        docker_build_cmd = [
            "docker",
            "build",
            "--progress=plain",
            "-t",
            self.image_name,
            "-f",
            self.dockerfile_path,
            self.project_root,
        ]
        if self.no_cache:
            docker_build_cmd.append("--no-cache")

        # Regex to strip ANSI escape sequences for storing logs as plain text
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

        if sys.platform == "win32":
            click.echo(
                click.style("Detected Windows: skipping PTY usage.", fg="yellow")
            )
            try:
                process = subprocess.Popen(
                    docker_build_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                build_logs = []

                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        clean_text = ansi_escape.sub("", line)
                        build_logs.append(clean_text)
                        # ローカル表示用にカラーをつけて出力
                        colored_chunk = click.style(clean_text, fg="blue")
                        sys.stdout.write(colored_chunk)
                        sys.stdout.flush()

                err_text = process.stderr.read()
                if err_text:
                    clean_text = ansi_escape.sub("", err_text)
                    build_logs.append(clean_text)
                    colored_chunk = click.style(clean_text, fg="blue")
                    sys.stdout.write(colored_chunk)
                    sys.stdout.flush()

                return_code = process.wait()
                if return_code != 0:
                    all_logs = "".join(build_logs)
                    raise subprocess.CalledProcessError(
                        return_code, docker_build_cmd, output=all_logs
                    )

                click.echo(
                    click.style(
                        f"Docker image '{self.image_name}' built successfully.",
                        fg="green",
                    )
                )
                return "".join(build_logs)

            except subprocess.CalledProcessError as e:
                click.echo(
                    click.style(
                        f"Error building Docker image '{self.image_name}': {e.output}",
                        fg="red",
                    )
                )
                sys.exit(1)
            except Exception as e:
                click.echo(
                    click.style(
                        f"Unexpected error while building Docker image: {str(e)}",
                        fg="red",
                    )
                )
                sys.exit(1)

        else:
            try:
                import pty

                master_fd, slave_fd = pty.openpty()

                process = subprocess.Popen(
                    docker_build_cmd,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    text=False,
                    bufsize=0,
                )

                os.close(slave_fd)

                build_logs = []

                while True:
                    r, _, _ = select.select([master_fd], [], [], 0.1)
                    if master_fd in r:
                        try:
                            chunk = os.read(master_fd, 1024)
                        except OSError:
                            break
                        if not chunk:
                            break
                        text_chunk = chunk.decode(errors="replace")
                        clean_text = ansi_escape.sub("", text_chunk)
                        build_logs.append(clean_text)
                        colored_chunk = click.style(clean_text, fg="blue")
                        sys.stdout.write(colored_chunk)
                        sys.stdout.flush()

                    if process.poll() is not None:
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

                os.close(master_fd)
                return_code = process.wait()
                if return_code != 0:
                    all_logs = "".join(build_logs)
                    raise subprocess.CalledProcessError(
                        return_code, docker_build_cmd, output=all_logs
                    )

                click.echo(
                    click.style(
                        f"Docker image '{self.image_name}' built successfully.",
                        fg="green",
                    )
                )
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
                        f"Unexpected error while building Docker image: {str(e)}",
                        fg="red",
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
