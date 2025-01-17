import configparser
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, List, Optional

import click
from dotenv import dotenv_values, load_dotenv

from morph.cli.flags import Flags
from morph.constants import MorphConstant
from morph.task.base import BaseTask
from morph.task.utils.morph import find_project_root_dir
from morph.task.utils.timezone import TimezoneManager


class ApiTask(BaseTask):
    def __init__(self, args: Flags):
        super().__init__(args)
        self.args = args

        # port
        self.server_port = self._find_available_port(8080)
        os.environ["MORPH_SERVER_PORT"] = str(self.server_port)
        self.front_port = self._find_available_port(3000)
        os.environ["MORPH_FRONT_PORT"] = str(self.front_port)

        # change working directory if specified
        self.workdir = args.WORKDIR
        if self.workdir:
            os.chdir(self.workdir)
        else:
            self.workdir = os.getcwd()

        self.is_preview = args.PREVIEW or False
        os.environ["MORPH_LOCAL_DEV_MODE"] = "false" if self.args.PREVIEW else "true"

        config_path = MorphConstant.MORPH_CRED_PATH
        has_config = os.path.exists(config_path)

        if has_config:
            # read credentials
            config = configparser.ConfigParser()
            config.read(config_path)
            if not config.sections():
                click.echo(
                    click.style(
                        f"Error: No credentials entries found in {config_path}.",
                        fg="red",
                        bg="yellow",
                    )
                )
                sys.exit(1)  # 1: General errors

            # set api key
            self.api_key: str = config.get("default", "api_key", fallback="")
            os.environ["MORPH_API_KEY"] = self.api_key

        # load environment variables from .env file
        project_root = find_project_root_dir()
        dotenv_path = os.path.join(project_root, ".env")
        load_dotenv(dotenv_path)
        env_vars = dotenv_values(dotenv_path)
        for e_key, e_val in env_vars.items():
            os.environ[e_key] = str(e_val)

        # set timezone if specified
        desired_tz = os.getenv("TZ")
        if desired_tz is not None:
            tz_manager = TimezoneManager()
            if not tz_manager.is_valid_timezone(desired_tz):
                click.echo(
                    click.style(
                        f"Warning: Invalid TZ value in .env. Falling back to {tz_manager.get_current_timezone()}.",
                        fg="yellow",
                    ),
                    err=False,
                )
            if desired_tz != tz_manager.get_current_timezone():
                tz_manager.set_timezone(desired_tz)

        # for managing subprocesses
        self.processes: List[subprocess.Popen[str]] = []

    def _find_available_port(self, start_port: int, max_port: int = 65535) -> int:

        port = start_port

        while port <= max_port:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("0.0.0.0", port)) != 0:
                    return port
            port += 1

        click.echo(
            click.style(
                f"Error: No available port found in range {start_port}-{max_port}.",
                fg="red",
            )
        )
        sys.exit(1)

    def run(self):
        current_dir = Path(__file__).resolve().parent
        server_script_path = os.path.join(current_dir, "server.py")

        signal.signal(signal.SIGINT, self._signal_handler)
        try:
            click.echo(
                click.style(
                    "🚀 Starting Morph server...",
                    fg="green",
                )
            )

            # run frontend
            self._run_frontend()

            # run server process
            self._run_process(
                [sys.executable, server_script_path]
                + sys.argv[1:]
                + ["--port", str(self.server_port)],
            )

            click.echo(
                click.style(
                    "✅ Done server setup",
                    fg="green",
                )
            )

            running_url = f"http://localhost:{self.server_port}"
            click.echo(
                click.style(
                    f"\nMorph is running!🚀\n\n ->  Local: {running_url}\n",
                    fg="yellow",
                )
            )
            signal.pause()
        except KeyboardInterrupt:
            self._signal_handler(None, None)

    def _run_frontend(self) -> None:
        frontend_dir = os.path.join(self.workdir, ".morph", "frontend")
        if not os.path.exists(frontend_dir):
            frontend_template_path = (
                Path(__file__).parents[1].joinpath("frontend", "template")
            )

            shutil.copytree(frontend_template_path, frontend_dir)

        try:
            subprocess.run(
                "npm install",
                cwd=frontend_dir,
                shell=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            click.echo(
                click.style("Failed to install frontend dependencies.", fg="yellow")
            )
            exit(1)

        if self.is_preview:
            subprocess.run(
                ["npm", "run", "build"],
                cwd=frontend_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
        else:
            self._run_process(
                ["npm", "run", "dev", "--port", f"{self.front_port}"],
                cwd=frontend_dir,
                is_debug=False,
            )

    def _run_process(
        self,
        command: List[str],
        cwd: Optional[str] = None,
        is_debug: Optional[bool] = True,
    ) -> None:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE if is_debug else subprocess.DEVNULL,
            stderr=subprocess.PIPE if is_debug else subprocess.DEVNULL,
            text=True,
        )

        def log_output(pipe):
            for line in iter(pipe.readline, ""):
                color = _get_color_for_log_level(line)
                for sub_line in line.splitlines():
                    click.echo(
                        click.style(
                            sub_line,
                            fg=color,
                        ),
                        err=False,
                    )

        def _get_color_for_log_level(line: str) -> str:
            if "ERROR" in line:
                return "red"
            elif "WARNING" in line:
                return "yellow"
            elif "DEBUG" in line:
                return "blue"
            elif "INFO" in line:
                return "green"
            else:
                return "white"

        if is_debug:
            threading.Thread(target=log_output, args=(process.stdout,)).start()
            threading.Thread(target=log_output, args=(process.stderr,)).start()

        self.processes.append(process)

    def _terminate_processes(self) -> None:
        for process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception as e:
                click.echo(
                    click.style(
                        f"Error terminating process {process.pid}: {e}",
                        fg="red",
                    ),
                    err=True,
                )
            finally:
                try:
                    process.kill()
                except:  # noqa
                    pass

    def _signal_handler(self, sig: Any, frame: Any) -> None:
        self._terminate_processes()
        sys.exit(0)
