import configparser
import os
import signal
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


class BuildTask(BaseTask):
    def __init__(self, args: Flags):
        super().__init__(args)
        self.args = args

        self.workdir = args.WORKDIR
        if self.workdir and self.workdir != "":
            os.chdir(self.workdir)
        self.is_debug = self.args.NO_LOG is False

        os.environ["MORPH_FRONT_BUILD"] = "true"

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

            self.team_slug: str = config.get("default", "team_slug", fallback="")
            self.app_url: str = config.get("default", "app_url", fallback="")
            self.workspace_id: str = config.get(
                "default", "workspace_id", fallback=""
            ) or config.get("default", "database_id", fallback="")
            self.api_key: str = config.get("default", "api_key", fallback="")

            os.environ["MORPH_WORKSPACE_ID"] = self.workspace_id
            os.environ["MORPH_BASE_URL"] = self.app_url
            os.environ["MORPH_TEAM_SLUG"] = self.team_slug
            os.environ["MORPH_API_KEY"] = self.api_key

        project_root = find_project_root_dir()
        dotenv_path = os.path.join(project_root, ".env")
        load_dotenv(dotenv_path)
        env_vars = dotenv_values(dotenv_path)
        for e_key, e_val in env_vars.items():
            os.environ[e_key] = str(e_val)

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

        self.processes: List[subprocess.Popen[str]] = []

    def run(self):
        self._setup_frontend()

        current_dir = Path(__file__).resolve().parent
        server_script_path = os.path.join(current_dir, "server.py")

        self._start_frontend()

        signal.signal(signal.SIGINT, self._signal_handler)
        try:
            self._run_process(
                [sys.executable, server_script_path] + sys.argv[1:],
                log=self.is_debug,
            )

            click.echo(
                click.style(
                    "✅ Done setup",
                    fg="green",
                )
            )

            running_url = f"http://localhost:{self.args.PORT}"
            click.echo(
                click.style(
                    f"\nMorph is ready!🚀\n\n ->  Local: {running_url}\n",
                    fg="yellow",
                )
            )
            signal.pause()
        except KeyboardInterrupt:
            self._signal_handler(None, None)

    def _setup_frontend(self) -> None:
        click.echo(
            click.style(
                "Building in progress ...",
                fg="green",
            )
        )
        current_dir = Path(__file__).resolve()
        frontend_dir = os.path.join(current_dir.parents[1], "frontend")

        constants_file = os.path.join(frontend_dir, "constants.js")
        constants_base_file = os.path.join(frontend_dir, "constants-base.js")

        rel_from_frontend_path = os.path.relpath(os.getcwd(), frontend_dir)
        pages_dir_from_frontend_path = os.path.join(
            rel_from_frontend_path, "src", "pages"
        )
        with open(constants_base_file, "r") as f:
            c_content = f.read()
            c_content = c_content.replace(
                "%PAGES_GLOB_BASE_DIR_PATH_FROM_FRONTEND_ROOT%",
                pages_dir_from_frontend_path,
            )
        with open(constants_file, "w", encoding="utf-8") as f:
            f.write(c_content)

        subprocess.run(
            ["npm", "install"],
            cwd=frontend_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True,
        )

    def _start_frontend(self) -> None:
        current_dir = Path(__file__).resolve()
        frontend_dir = os.path.join(current_dir.parents[1], "frontend")

        subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )

    def _run_process(
        self, command: List[str], cwd: Optional[str] = None, log: Optional[bool] = True
    ) -> None:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE if log else subprocess.DEVNULL,
            stderr=subprocess.PIPE if log else subprocess.DEVNULL,
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

        if log:
            threading.Thread(
                target=log_output, args=(process.stdout,), daemon=True
            ).start()
            threading.Thread(
                target=log_output, args=(process.stderr,), daemon=True
            ).start()

        self.processes.append(process)

    def _terminate_processes(self) -> None:
        for process in self.processes:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                click.echo(
                    click.style(
                        f"Process {process.pid} did not terminate within 5 seconds. Forcing termination.",
                        fg="yellow",
                    ),
                    err=True,
                )
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception as e:
                click.echo(
                    click.style(
                        f"Unexpected error while terminating process {process.pid}: {e}",
                        fg="red",
                    ),
                    err=True,
                )

    def _signal_handler(self, sig: Any, frame: Any) -> None:
        self._terminate_processes()
        sys.exit(0)
