# type: ignore

from __future__ import annotations

import functools
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
@click.version_option(
    package_name="morph-data",
    prog_name="morph",
    message="morph-data CLI version: %(version)s",
)
@click.pass_context
@global_flags
def cli(ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]) -> None:
    """A data analysis tool for transformations, visualization by using SQL and Python.
    For more information on these commands, visit: docs.morph-data.io
    """


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
@params.project_id
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


@cli.command("clean")
@params.verbose
@params.force
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


@cli.command("deploy")
@params.no_cache
@params.verbose
@click.pass_context
@global_flags
@requires.preflight
@requires.postflight
def deploy(
    ctx: click.Context, no_cache: bool, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[Union[Dict[str, Union[str, int, bool]], None], bool]:
    """Deploy morph project to the cloud."""
    from morph.task.deploy import DeployTask

    task = DeployTask(ctx.obj["flags"])
    results = task.run()
    return results, True


@cli.command("serve")
@params.workdir
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


@cli.command("context")
@params.output
@click.pass_context
@global_flags
@requires.preflight
@requires.postflight
def context(
    ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[None, bool]:
    """Print or save the user information context."""
    from morph.task.context import ContextTask

    task = ContextTask(ctx.obj["flags"])
    task.run()

    return None, True


@cli.command("add")
@click.argument("plugin_name", required=True)
@click.pass_context
@global_flags
@requires.preflight
@requires.postflight
def add_plugin(
    ctx: click.Context, **kwargs: Dict[str, Union[str, int, bool]]
) -> Tuple[None, bool]:
    """Add a plugin to your project."""
    from morph.task.plugin import PluginTask

    task = PluginTask(ctx.obj["flags"])
    task.run()

    return None, True
