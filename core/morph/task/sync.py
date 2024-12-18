import configparser
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import List, Union

import click
import requests
from gitignore_parser import parse_gitignore

from morph.api.cloud.client import (
    MORPH_API_BASE_URL,
    MorphApiClient,
    MorphApiKeyClientImpl,
)
from morph.api.cloud.types import EnvVarObject
from morph.cli.flags import Flags
from morph.config.project import load_project
from morph.constants import MorphConstant
from morph.task.base import BaseTask
from morph.task.utils.morph import find_project_root_dir


def is_poetry_project(project_root):
    pyproject = Path(project_root) / "pyproject.toml"
    if not pyproject.exists():
        return False
    with open(pyproject, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("[tool.poetry]"):
                return True
    return False


def export_requirements_with_poetry(project_root, requirements_file):
    subprocess.run(
        [
            "poetry",
            "export",
            "-f",
            "requirements.txt",
            "--output",
            requirements_file,
            "--without-hashes",
        ],
        check=True,
        cwd=project_root,
    )


def export_requirements_with_pip(requirements_file):
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    with open(requirements_file, "w", encoding="utf-8") as f:
        f.write(result.stdout)


class SyncTask(BaseTask):
    def __init__(self, args: Flags):
        super().__init__(args)
        self.args = args
        self.is_verbose = args.VERBOSE

        # Warn user that this command will override file in the VM
        if (
            input(
                "This command will override files in the VM with local files. Are you sure you want to proceed? (Y/n): ",
            )
            != "Y"
        ):
            click.echo(click.style("Aborted!"))
            sys.exit(1)  # 1: General errors

        try:
            self.project_root = find_project_root_dir(os.getcwd())
        except FileNotFoundError as e:
            click.echo(click.style(str(e), fg="red", bg="yellow"))
            sys.exit(1)  # 1: General errors

        # Check .env file in the project root
        self.env_file = os.path.join(self.project_root, ".env")
        if os.path.exists(self.env_file):
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
                sys.exit(1)  # 1: General errors

        # Warn if there is no requirements.txt file
        requirements_file = os.path.join(self.project_root, "requirements.txt")
        if not os.path.exists(requirements_file):
            click.echo(
                click.style(
                    "Warning: No requirements.txt file found in the project root. Uploading files without dependencies.",
                    fg="yellow",
                )
            )

        # Check if the .morph directory exists
        morph_dir = MorphConstant.INIT_DIR
        if not os.path.exists(morph_dir):
            click.echo(
                click.style(
                    "Error: Morph CLI has not been initialized. Please run 'morph config' first.",
                    fg="red",
                    bg="yellow",
                )
            )
            sys.exit(1)  # 1: General errors

        # Load ~/.morph/credentials file
        config = configparser.ConfigParser()
        cred_file = os.path.join(morph_dir, "credentials")
        if not os.path.exists(cred_file):
            click.echo(
                click.style(
                    "Error: No credentials found. Please run 'morph config' first.",
                    fg="red",
                    bg="yellow",
                )
            )
            sys.exit(1)  # 1: General errors

        # Load project settings from morph_project.yml
        project = load_project(self.project_root)
        profile = project.profile if project and project.profile else "default"

        # Parse credentials file
        config.read(cred_file)
        if not config.has_section(profile):
            click.echo(
                click.style(
                    f"Error: No {profile} section found in credentials. Please review your morph_project.yml file and run 'morph config' again.",
                    fg="red",
                    bg="yellow",
                )
            )
            sys.exit(1)  # 1: General errors

        self.app_url = (
            config.get(profile, "app_url", fallback=None) or MORPH_API_BASE_URL
        )
        self.workspace_id = config.get(
            profile, "workspace_id", fallback=None
        ) or config.get(profile, "database_id", fallback=None)
        self.api_key = config.get(profile, "api_key", fallback=None)

        if not self.app_url or not self.workspace_id or not self.api_key:
            click.echo(
                click.style(
                    "Error: Missing configuration settings. Please review your morph_project.yml file and run 'morph config' again.",
                    fg="red",
                    bg="yellow",
                )
            )
            sys.exit(1)  # 1: General errors

    def run(self):
        # Check VM status and start it if it is not running
        vm_status_url = f"{self.app_url}/{self.workspace_id}/vm"
        vm_status_response = requests.get(
            vm_status_url, headers={"x-api-key": self.api_key}
        )
        if vm_status_response.status_code != 200:
            click.echo(
                click.style(
                    f"Error: Failed to get VM status. {vm_status_response.status_code} - {vm_status_response.reason}",
                    fg="red",
                    bg="yellow",
                ),
                nl=False,
            )
            sys.exit(1)  # 1: General errors

        vm_api_url: Union[str, None] = None
        is_vm_exist: bool = False
        needs_shutdown: bool = (
            False  # VM launched by cli needs to be shutdown after sync
        )
        if isinstance(vm_status_response.json(), list):
            vm_status = [
                v for v in vm_status_response.json() if v.get("type") == "private"
            ][0]
            vm_api_url = vm_status.get("publicUri")
            is_vm_exist = vm_status.get("isExist")

        if not is_vm_exist:
            click.echo("Initializing Morph cloud environment...", nl=False)
            start_vm_response = requests.post(
                vm_status_url, json={}, headers={"x-api-key": self.api_key}
            )
            vm_api_url = start_vm_response.json().get("publicUri")
            if start_vm_response.status_code != 200:
                click.echo("")
                click.echo(
                    click.style(
                        f"Error: Failed to start the VM. {start_vm_response.status_code} - {start_vm_response.reason}",
                        fg="red",
                        bg="yellow",
                    )
                )
                sys.exit(1)  # 1: General errors

            max_retries = 60
            retry_interval = 1
            for retry in range(max_retries):
                vm_status_response = requests.get(
                    vm_status_url, headers={"x-api-key": self.api_key}
                )
                if vm_status_response.status_code != 200:
                    click.echo("")
                    click.echo(
                        click.style(
                            f"Error: Failed to get VM status. {vm_status_response.status_code} - {vm_status_response.reason}",
                            fg="red",
                            bg="yellow",
                        )
                    )
                    sys.exit(1)  # 1: General errors

                if isinstance(vm_status_response.json(), list):
                    vm_status = [
                        v
                        for v in vm_status_response.json()
                        if v.get("type") == "private"
                    ][0]
                    vm_api_url = vm_status.get("publicUri")
                    is_vm_exist = vm_status.get("isExist")

                if is_vm_exist:
                    # Slightly delay to allow VM to fully start
                    needs_shutdown = True
                    delay = 12
                    for i in range(delay):
                        click.echo(".", nl=False)
                        time.sleep(1)

                    click.echo(click.style(" done!", fg="green"))
                    break

                click.echo(".", nl=False)
                time.sleep(retry_interval)
            else:
                click.echo(
                    click.style(
                        "Error: VM did not start within the expected time.",
                        fg="red",
                        bg="yellow",
                    )
                )
                click.echo("")
                sys.exit(1)  # 1: General errors

        if vm_api_url is None:
            click.echo(
                click.style(
                    "Error: VM API URL is not found.",
                    fg="red",
                    bg="yellow",
                )
            )
            sys.exit(1)  # 1: General errors

        # Retrieve all the files from user VM (gzip tarball)
        vm_api_url = f"https://{vm_api_url}"
        click.echo("Pulling files from Morph cloud environment...", nl=False)
        try:
            response = requests.post(
                f"{vm_api_url}/fs/workdir/download",
                headers={"x-api-key": self.api_key},
                stream=True,
            )
            if response.status_code != 200:
                click.echo("")
                click.echo(
                    click.style(
                        f"Error: Failed to retrieve files from VM. {response.status_code} - {response.reason}",
                        fg="red",
                        bg="yellow",
                    )
                )
                if needs_shutdown:
                    self.shutdown_vm()
                sys.exit(1)  # 1: General errors

            # Create temporary directory to store extracted files
            vm_tmp_dir = tempfile.mkdtemp()

            # Write tar.gz content to a temp file
            tarball_path = os.path.join(vm_tmp_dir, "workdir.tar.gz")
            with open(tarball_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract tar.gz into vm_tmp_dir
            with tarfile.open(tarball_path, "r:gz") as tar:
                tar.extractall(path=vm_tmp_dir)

            # Remove the tarball after extraction
            os.remove(tarball_path)

            click.echo(click.style(" done!", fg="green"))
        except requests.RequestException as e:
            click.echo("")
            click.echo(
                click.style(
                    f"Error: Unable to retrieve files from VM. {str(e)}",
                    fg="red",
                    bg="yellow",
                )
            )
            if needs_shutdown:
                self.shutdown_vm()
            sys.exit(1)  # 1: General errors

        # Check if .gitignore exists in the project root
        gitignore_path = os.path.join(self.project_root, ".gitignore")
        if os.path.exists(gitignore_path):
            is_ignored = parse_gitignore(gitignore_path)
        else:
            is_ignored = None

        # Apply .gitignore rules to VM files
        if is_ignored is not None:
            for root, dirs, files in os.walk(vm_tmp_dir, topdown=True):
                dirs_copy = dirs[:]
                for dir_name in dirs_copy:
                    dir_path = os.path.join(root, dir_name)
                    relative_path = os.path.relpath(dir_path, vm_tmp_dir)
                    if dir_name == ".git" or is_ignored(relative_path):
                        shutil.rmtree(dir_path)
                        dirs.remove(dir_name)
                files_copy = files[:]
                for file_name in files_copy:
                    file_path = os.path.join(root, file_name)
                    relative_path = os.path.relpath(file_path, vm_tmp_dir)
                    if is_ignored(relative_path):
                        os.remove(file_path)

        # Merge VM files and local files
        # We copy local files to vm_tmp_dir to overwrite VM files
        # If there's a conflict, local files take precedence
        click.echo("Uploading files to Morph cloud environment...", nl=False)
        for root, dirs, files in os.walk(self.project_root, topdown=True):
            dirs_copy = dirs[:]
            for dir_name in dirs_copy:
                dir_path = os.path.join(root, dir_name)
                relative_path = os.path.relpath(dir_path, self.project_root)
                if dir_name == ".git" or (
                    is_ignored is not None and is_ignored(relative_path)
                ):
                    dirs.remove(dir_name)
            for file_name in files:
                local_file_path = os.path.join(root, file_name)
                relative_path = os.path.relpath(local_file_path, self.project_root)
                if is_ignored is not None and is_ignored(relative_path):
                    continue
                vm_file_path = os.path.join(vm_tmp_dir, relative_path)
                vm_dir = os.path.dirname(vm_file_path)
                if not os.path.exists(vm_dir):
                    os.makedirs(vm_dir, exist_ok=True)
                shutil.copy2(local_file_path, vm_file_path)

        # Tarball all merged files in vm_tmp_dir
        merged_tarball_path = os.path.join(vm_tmp_dir, "updated_workdir.tar.gz")
        with tarfile.open(merged_tarball_path, "w:gz") as tar:
            tar.add(vm_tmp_dir, arcname=".")

        # Upload the merged tarball to VM
        with open(merged_tarball_path, "rb") as f:
            upload_response = requests.post(
                f"{vm_api_url}/fs/workdir/upload",
                headers={"x-api-key": self.api_key, "Content-Type": "application/gzip"},
                data=f,
            )
        if upload_response.status_code != 200:
            click.echo("")
            click.echo(
                click.style(
                    f"Error: Failed to upload merged files to VM. {upload_response.status_code} - {upload_response.reason}",
                    fg="red",
                    bg="yellow",
                )
            )
            if needs_shutdown:
                self.shutdown_vm()
            sys.exit(1)  # 1: General errors

        # Clean up merged tarball
        os.remove(merged_tarball_path)
        click.echo(click.style(" done!", fg="green"))

        # Overwrite environment variables in the Morph Cloud with local .env file
        if os.path.exists(self.env_file):
            click.echo("Overwriting environment variables...", nl=False)
            env_vars: List[EnvVarObject] = []
            with open(self.env_file, "r") as f:
                for line in f:
                    if not line.strip() or line.startswith("#"):
                        continue
                    key, value = line.strip().split("=", 1)
                    env_vars.append(EnvVarObject(key=key, value=value))

            client = MorphApiClient(MorphApiKeyClientImpl)
            override_res = client.req.override_env_vars(env_vars=env_vars)
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

        # Clean up temporary directory
        shutil.rmtree(vm_tmp_dir)

        if needs_shutdown:
            self.shutdown_vm()

        click.echo(click.style("All files have been synchronized! 🎉", fg="green"))
        sys.exit(0)  # 0: Success

    def shutdown_vm(self):
        """
        Shutdown the VM after sync is completed.
        i.e., VM launched by cli needs to be shutdown after sync.
        """
        vm_url = f"{self.app_url}/{self.workspace_id}/vm"
        vm_response = requests.delete(vm_url, headers={"x-api-key": self.api_key})
        if vm_response.status_code != 200:
            click.echo(
                click.style(
                    f"Waring: Failed to shutdown VM. {vm_response.status_code} - {vm_response.reason}",
                    fg="yellow",
                ),
                nl=False,
            )
