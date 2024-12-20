# type: ignore

from __future__ import annotations

import functools
import importlib.metadata
from typing import Callable, Dict, Optional, Tuple, Union

import click

from morph.cli import params, requires
from morph.cli.flags import check_version_warning


def global_flags(
    func: Callable[..., Tuple[Union[Dict[str, Union[str, int, bool]], None], bool]]
) -> Callable[..., Tuple[Union[Dict[str, Union[str, int, bool]], None], bool]]:
    @params.log_format
    @functools.wraps(func)
    def wrapper(
        *args: Tuple[Union[Dict[str, Union[str, int, bool]], None], bool],
        **kwargs: Dict[str, Union[str, int, bool]],
    ) -> Tuple[Union[Dict[str, Union[str, int, bool]], None], bool]:
        ctx = click.get_current_context()

        if ctx.info_name == "serve":
            # Warn about version before running the command
            check_version_warning()
        else:
            # Warn about version after running the command
            ctx.call_on_close(check_version_warning)

        return func(*args, **kwargs)

    return wrapper


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
    no_args_is_help=True,
    epilog="Specify one of these sub-commands and you can find more help from there.",
)
@click.pass_context
@global_flags
def cli(ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]) -> None:
    """An data analysis tool for transformations, visualization by using SQL and Python.
    For more information on these commands, visit: docs.morph-data.io
    """


@cli.command("version")
def version() -> None:
    """Show the current morph-data CLI version."""
    try:
        current_version = importlib.metadata.version("morph-data")
        click.echo(f"morph-data CLI version: {current_version}")
    except importlib.metadata.PackageNotFoundError:
        click.echo(click.style("Error: morph-data is not installed.", fg="red"))


@cli.command("config")
@params.profile
@click.pass_context
@global_flags
@requires.preflight
@requires.postflight
def config(
    ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[Union[Dict[str, Union[str, int, bool]], None], bool]:
    """Configure morph credentials to run project."""
    from morph.task.config import ConfigTask

    task = ConfigTask(ctx.obj["flags"])
    results = task.run()
    return results, True


@cli.command("new")
@click.argument("directory_name", required=False)
@click.option(
    "--github-url",
    type=str,
    help="Specify the github URL to clone the workspace template.",
)
@click.option(
    "--directory",
    type=str,
    help="Specify the directory to clone the workspace template.",
)
@click.option(
    "--branch",
    type=str,
    default="main",
    show_default=True,
    help="Specify the branch to clone. Defaults to 'main'.",
)
@click.pass_context
@global_flags
@requires.preflight
@requires.postflight
def new(
    ctx: click.Context,
    directory_name: Optional[str],
    **kwargs: Dict[str, Union[str, int, bool]],
) -> Tuple[Union[Dict[str, Union[str, int, bool]], None], bool]:
    """Create a new morph project."""
    from morph.task.new import NewTask

    task = NewTask(ctx.obj["flags"], directory_name)
    results = task.run()
    return results, True


@cli.command("compile")
@click.option("--force", "-f", is_flag=True, help="Force compile.")
@click.pass_context
@global_flags
@params.verbose
@requires.preflight
@requires.postflight
def compile(
    ctx: click.Context, force: bool, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[None, bool]:
    """Analyse morph functions into indexable objects."""
    from morph.task.compile import CompileTask

    task = CompileTask(ctx.obj["flags"], force=force)
    task.run()
    return None, True


@cli.command("run")
@click.argument("filename", required=True)
@click.pass_context
@global_flags
@params.data
@params.run_id
@params.dag
@requires.preflight
@requires.postflight
def run(
    ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[Union[Dict[str, Union[str, int, bool]], None], bool]:
    """Run sql and python file and bring the results in output file."""
    from morph.task.run import RunTask

    task = RunTask(ctx.obj["flags"])
    results = task.run()

    return results, True


@cli.command("print")
@click.pass_context
@global_flags
@params.file
@params.alias
@params.all
@params.verbose
@requires.preflight
@requires.postflight
def print_resource(
    ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[Union[Dict[str, Union[str, int, bool]], None], bool]:
    """Print details for the specified resource by path or alias."""
    from morph.task.resource import PrintResourceTask

    task = PrintResourceTask(ctx.obj["flags"])
    results = task.run()
    return results, True


@cli.command("create")
@click.argument("filename", required=True)
@click.option("--template", type=str, help="Specify the template name.")
@click.option("--name", type=str, help="Specify the function name.")
@click.option("--description", type=str, help="Specify the function description.")
@click.option("--parent-name", type=str, help="Specify the parent function name.")
@click.option("--connection", type=str, help="Specify the connection name.")
@params.verbose
@click.pass_context
@global_flags
@requires.preflight
@requires.postflight
def create(
    ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[None, bool]:
    """Create files, using global or user defined templates."""
    from morph.task.create import CreateTask

    task = CreateTask(ctx.obj["flags"])
    task.run()

    return None, True


@cli.command("clean")
@params.verbose
@click.pass_context
@global_flags
@requires.preflight
@requires.postflight
def clean(
    ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[None, bool]:
    """Clean all the cache and garbage in Morph project."""
    from morph.task.clean import CleanTask

    task = CleanTask(ctx.obj["flags"])
    task.run()

    return None, True


@cli.command("sync")
@params.verbose
@click.pass_context
@global_flags
@requires.preflight
@requires.postflight
def sync(
    ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[Union[Dict[str, Union[str, int, bool]], None], bool]:
    """Synchronize local morph project with the cloud."""
    from morph.task.sync import SyncTask

    task = SyncTask(ctx.obj["flags"])
    results = task.run()
    return results, True


@cli.command("serve")
@params.port
@params.host
@params.restart
@params.workdir
@params.stop
@params.build
@params.no_log
@click.pass_context
@global_flags
@requires.preflight
@requires.postflight
def serve(
    ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[None, bool]:
    """Launch API server."""
    from morph.task.api import ApiTask

    task = ApiTask(ctx.obj["flags"])
    task.run()

    return None, True


@cli.command("init")
@click.pass_context
@global_flags
@requires.preflight
@requires.postflight
def init(
    ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[Union[Dict[str, Union[str, int, bool]], None], bool]:
    """Initialize morph connection setting to run project."""
    from morph.task.init import InitTask

    task = InitTask(ctx.obj["flags"])
    results = task.run()
    return results, True
