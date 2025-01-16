import configparser
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, List, Optional

import click
import psutil
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

        self.workdir = args.WORKDIR
        if self.workdir and self.workdir != "":
            os.chdir(self.workdir)
        self.is_debug = self.args.NO_LOG is False

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

            self.api_key: str = config.get("default", "api_key", fallback="")
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
        if self.args.STOP:
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    for conn in proc.net_connections(kind="inet"):
                        if conn.status == "LISTEN" and (
                            conn.laddr.port == self.args.PORT or conn.laddr.port == 3000
                        ):
                            try:
                                proc.terminate()
                            except psutil.AccessDenied:  # noqa
                                click.echo(
                                    click.style(
                                        f"Error: access denied process {proc.pid}.",
                                        fg="yellow",
                                    ),
                                    err=False,
                                )
                                exit(1)
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):  # noqa
                    pass
        elif self.args.RESTART:
            for proc in psutil.process_iter(attrs=["pid", "name"]):
                try:
                    for conn in proc.net_connections(kind="inet"):
                        if (
                            conn.status == "LISTEN"
                            and conn.laddr.port == self.args.PORT
                            or conn.laddr.port == 3000
                        ):
                            try:
                                proc.terminate()
                            except psutil.AccessDenied:  # noqa
                                click.echo(
                                    click.style(
                                        f"Error: access denied process {proc.pid}.",
                                        fg="yellow",
                                    ),
                                    err=False,
                                )
                                exit(1)
                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ):  # noqa
                    pass

            retry_cnt = 0
            retry_max = 5
            while retry_cnt < retry_max:
                try:
                    click.echo(
                        click.style(
                            "Restarting server...",
                            fg="yellow",
                        ),
                        err=False,
                    )
                    time.sleep(2)
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind((self.args.HOST, int(self.args.PORT)))
                    break
                except OSError as e:
                    if "Address already in use" in str(e):
                        retry_cnt += 1
                        click.echo(
                            click.style(
                                f"Warning: Port {self.args.PORT} is already in use. Retrying... ({retry_cnt}/{retry_max})",
                                fg="yellow",
                            ),
                            err=False,
                        )
                    else:
                        click.echo(
                            click.style(
                                f"Error: Failed to restart server: {str(e)}",
                                fg="yellow",
                            ),
                            err=True,
                        )
                        exit(1)
            err = False
            try:
                self._serve()
            except Exception as e:
                err = True
                click.echo(
                    click.style(
                        f"Error: Failed to restart server: {str(e)}",
                        fg="yellow",
                    ),
                    err=True,
                )
            finally:
                if not err:
                    click.echo(
                        click.style(
                            "Successfully restarted server! 🚀",
                            fg="yellow",
                        ),
                        err=False,
                    )
        else:
            self._serve()

    def _serve(self) -> None:
        current_dir = Path(__file__).resolve().parent
        server_script_path = os.path.join(current_dir, "server.py")

        signal.signal(signal.SIGINT, self._signal_handler)
        try:
            self._run_process(
                [sys.executable, server_script_path] + sys.argv[1:],
                log=self.is_debug,
            )

            click.echo(
                click.style(
                    "✅ Done server setup",
                    fg="green",
                )
            )

            if self.args.PREVIEW:
                running_url = f"http://localhost:{self.args.PORT}"
                click.echo(
                    click.style(
                        f"\nMorph is ready in preview mode!🚀\n\n ->  Local: {running_url}\n",
                        fg="yellow",
                    )
                )
            else:
                self._setup_frontend_for_dev()

                frontend_dir = os.path.join(os.getcwd(), ".morph", "frontend")

                subprocess.run(
                    ["npm", "install"],
                    cwd=frontend_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    check=True,
                )

                self._run_process(
                    ["npm", "run", "dev"],
                    cwd=frontend_dir,
                    log=False,
                )
                running_url = f"http://localhost:{self.args.PORT}"
                click.echo(
                    click.style(
                        f"\nMorph is ready in development mode!🚀\n\n ->  Local: {running_url}\n",
                        fg="yellow",
                    )
                )
            signal.pause()
        except KeyboardInterrupt:
            self._signal_handler(None, None)

    def _setup_frontend_for_dev(self) -> None:
        project_root = find_project_root_dir()

        if not os.path.exists(f"{project_root}/.morph/frontend"):
            frontend_template_path = (
                Path(__file__).parents[1].joinpath("frontend", "template")
            )

            shutil.copytree(frontend_template_path, f"{project_root}/.morph/frontend")

            try:
                subprocess.run(
                    f"cd {project_root}/.morph/frontend && npm install",
                    shell=True,
                    check=True,
                )
            except subprocess.CalledProcessError:
                click.echo(
                    click.style("Failed to install frontend dependencies.", fg="yellow")
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
