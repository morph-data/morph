import importlib.metadata
import os
import sys
from argparse import Namespace
from dataclasses import dataclass
from pprint import pformat as pf
from typing import Any, Callable, Dict, List, Optional, Set, Union

import click
import requests
from click import Context, Parameter, get_current_context
from click.core import Command as ClickCommand
from click.core import Group, ParameterSource
from packaging.version import InvalidVersion, Version

from morph.cli.types import Command as CliCommand

if os.name != "nt":
    # https://bugs.python.org/issue41567
    import multiprocessing.popen_spawn_posix  # noqa: F401

FLAGS_DEFAULTS = {
    "INDIRECT_SELECTION": "eager",
    "TARGET_PATH": None,
    "DEFER_STATE": None,  # necessary because of retry construction of flags
    "WARN_ERROR": None,
}

DEPRECATED_PARAMS = {
    "deprecated_defer": "defer",
    "deprecated_favor_state": "favor_state",
    "deprecated_print": "print",
    "deprecated_state": "state",
}

WHICH_KEY = "which"

GLOBAL_FLAGS = Namespace(USE_COLORS=True)


def set_flags(flags):
    global GLOBAL_FLAGS
    GLOBAL_FLAGS = flags


def args_to_context(args: List[str]) -> Context:
    """Convert a list of args to a click context with proper hierarchy for morph commands"""
    from morph.cli.main import cli  # type: ignore

    cli_ctx = cli.make_context(cli.name, args)
    # Split args if they're a comma separated string.
    if len(args) == 1 and "," in args[0]:
        args = args[0].split(",")
    sub_command_name, sub_command, args = cli.resolve_command(cli_ctx, args)
    # Handle source and docs group.
    if isinstance(sub_command, Group):
        sub_command_name, sub_command, args = sub_command.resolve_command(cli_ctx, args)

    assert isinstance(sub_command, ClickCommand)
    sub_command_ctx = sub_command.make_context(sub_command_name, args)
    sub_command_ctx.parent = cli_ctx
    return sub_command_ctx


@dataclass(frozen=True)
class Flags:
    """Primary configuration artifact for running morph"""

    def __init__(self, ctx: Optional[Context] = None) -> None:
        # Set the default flags.
        for key, value in FLAGS_DEFAULTS.items():
            object.__setattr__(self, key, value)

        if ctx is None:
            ctx = get_current_context()

        def _get_params_by_source(ctx: Context, source_type: ParameterSource):  # type: ignore
            """Generates all params of a given source type."""
            yield from [
                name
                for name, source in ctx._parameter_source.items()
                if source is source_type
            ]
            if ctx.parent:
                yield from _get_params_by_source(ctx.parent, source_type)

        # Ensure that any params sourced from the commandline are not present more than once.
        # Click handles this exclusivity, but only at a per-subcommand level.
        seen_params = []
        for param in _get_params_by_source(ctx, ParameterSource.COMMANDLINE):
            if param in seen_params:
                raise Exception(
                    f"{param.lower()} was provided both before and after the subcommand, it can only be set either before or after.",
                )
            seen_params.append(param)

        def _assign_params(  # type: ignore
            ctx: Context,
            params_assigned_from_default: set,
            params_assigned_from_user: set,
            deprecated_env_vars: Dict[str, Callable],
        ):
            """Recursively adds all click params to flag object"""
            for param_name, param_value in ctx.params.items():
                # N.B. You have to use the base MRO method (object.__setattr__) to set attributes
                # when using frozen dataclasses.
                # https://docs.python.org/3/library/dataclasses.html#frozen-instances

                # Handle deprecated env vars while still respecting old values
                new_name: Union[str, None] = None
                if param_name in DEPRECATED_PARAMS:
                    # Deprecated env vars can only be set via env var.
                    # We use the deprecated option in click to serialize the value
                    # from the env var string.
                    param_source = ctx.get_parameter_source(param_name)
                    if param_source == ParameterSource.DEFAULT:
                        continue
                    elif param_source != ParameterSource.ENVIRONMENT:
                        raise Exception(
                            "Deprecated parameters can only be set via environment variables",
                        )

                    # Rename for clarity.
                    dep_name = param_name
                    new_name = DEPRECATED_PARAMS.get(dep_name)
                    try:
                        assert isinstance(new_name, str)
                    except AssertionError:
                        raise Exception(
                            f"No deprecated param name match in DEPRECATED_PARAMS from {dep_name} to {new_name}"
                        )

                    # Find param objects for their envvar name.
                    # try:
                    #     dep_param = [
                    #         x for x in ctx.command.params if x.name == dep_name
                    #     ][0]
                    #     new_param = [
                    #         x for x in ctx.command.params if x.name == new_name
                    #     ][0]
                    # except IndexError:
                    #     raise Exception(
                    #         f"No deprecated param name match in context from {dep_name} to {new_name}"
                    #     )

                    # Remove param from defaulted set since the deprecated
                    # value is not set from default, but from an env var.
                    if new_name in params_assigned_from_default:
                        params_assigned_from_default.remove(new_name)

                # Set the flag value.
                is_duplicate = hasattr(self, param_name.upper())
                is_default = (
                    ctx.get_parameter_source(param_name) == ParameterSource.DEFAULT
                )
                flag_name = (new_name or param_name).upper()

                if (is_duplicate and not is_default) or not is_duplicate:
                    object.__setattr__(self, flag_name, param_value)

                # Track default assigned params.
                if not is_default:
                    params_assigned_from_user.add(param_name)
                    if param_name in params_assigned_from_default:
                        params_assigned_from_default.remove(param_name)
                if is_default and param_name not in params_assigned_from_user:
                    params_assigned_from_default.add(param_name)

            if ctx.parent:
                _assign_params(
                    ctx.parent,
                    params_assigned_from_default,
                    params_assigned_from_user,
                    deprecated_env_vars,
                )

        params_assigned_from_user = set()  # type: Set[str]
        params_assigned_from_default = set()  # type: Set[str]
        deprecated_env_vars: Dict[str, Callable] = {}
        _assign_params(
            ctx,
            params_assigned_from_default,
            params_assigned_from_user,
            deprecated_env_vars,
        )

        # Set deprecated_env_var_warnings to be fired later after events have been init.
        object.__setattr__(
            self,
            "deprecated_env_var_warnings",
            [x for x in deprecated_env_vars.values()],
        )

        # Get the invoked command flags.
        from morph.cli.main import cli  # type: ignore

        (
            invoked_subcommand_name,
            invoked_subcommand,
            remaining_args,
        ) = cli.resolve_command(ctx, sys.argv[1:])

        if invoked_subcommand_name:
            invoked_subcommand_ctx = invoked_subcommand.make_context(
                invoked_subcommand_name, remaining_args
            )
            invoked_subcommand_ctx.parent = ctx
            _assign_params(
                invoked_subcommand_ctx,
                params_assigned_from_default,
                params_assigned_from_user,
                deprecated_env_vars,
            )

        # Set hard coded flags.
        object.__setattr__(self, "WHICH", invoked_subcommand_name or ctx.info_name)

        # Apply the lead/follow relationship between some parameters.
        self._override_if_set(
            "USE_COLORS", "USE_COLORS_FILE", params_assigned_from_default
        )
        self._override_if_set(
            "LOG_LEVEL", "LOG_LEVEL_FILE", params_assigned_from_default
        )
        self._override_if_set(
            "LOG_FORMAT", "LOG_FORMAT_FILE", params_assigned_from_default
        )

        # Support console DO NOT TRACK initiative.
        if os.getenv("DO_NOT_TRACK", "").lower() in ("1", "t", "true", "y", "yes"):
            object.__setattr__(self, "SEND_ANONYMOUS_USAGE_STATS", False)

        # Check mutual exclusivity once all flags are set.
        # self._assert_mutually_exclusive(
        #     params_assigned_from_default, ["WARN_ERROR", "WARN_ERROR_OPTIONS"]
        # )

    def __str__(self) -> str:
        return str(pf(self.__dict__))

    def _override_if_set(self, lead: str, follow: str, defaulted: Set[str]) -> None:
        """If the value of the lead parameter was set explicitly, apply the value to follow, unless follow was also set explicitly."""
        if lead.lower() not in defaulted and follow.lower() in defaulted:
            object.__setattr__(self, follow.upper(), getattr(self, lead.upper(), None))

    def _assert_mutually_exclusive(
        self, params_assigned_from_default: Set[str], group: List[str]
    ) -> None:
        """
        Ensure no elements from group are simultaneously provided by a user, as inferred from params_assigned_from_default.
        Raises click.UsageError if any two elements from group are simultaneously provided by a user.
        """
        set_flag = None
        for flag in group:
            flag_set_by_user = flag.lower() not in params_assigned_from_default
            if flag_set_by_user and set_flag:
                raise Exception(
                    f"{flag.lower()}: not allowed with argument {set_flag.lower()}"
                )
            elif flag_set_by_user:
                set_flag = flag

    def fire_deprecations(self):
        """Fires events for deprecated env_var usage."""
        [dep_fn() for dep_fn in self.deprecated_env_var_warnings]
        # It is necessary to remove this attr from the class so it does
        # not get pickled when written to disk as json.
        object.__delattr__(self, "deprecated_env_var_warnings")

    @classmethod
    def from_dict(cls, command: CliCommand, args_dict: Dict[str, Any]) -> "Flags":
        command_arg_list = command_params(command, args_dict)
        ctx = args_to_context(command_arg_list)
        flags = cls(ctx=ctx)
        flags.fire_deprecations()
        return flags

    # This is here to prevent mypy from complaining about all of the
    # attributes which we added dynamically.
    def __getattr__(self, name: str) -> Any:
        return super().__getattribute__(name)


CommandParams = List[str]


def command_params(command: CliCommand, args_dict: Dict[str, Any]) -> CommandParams:
    """Given a command and a dict, returns a list of strings representing
    the CLI params for that command. The order of this list is consistent with
    which flags are expected at the parent level vs the command level.

    e.g. fn("run", {"defer": True, "print": False}) -> ["--no-print", "run", "--defer"]

    The result of this function can be passed in to the args_to_context function
    to produce a click context to instantiate Flags with.
    """

    cmd_args = set(command_args(command))
    prnt_args = set(parent_args())
    default_args = set([x.lower() for x in FLAGS_DEFAULTS.keys()])

    res = command.to_list()
    for k, v in args_dict.items():
        k = k.lower()
        # if a "which" value exists in the args dict, it should match the command provided
        if k == WHICH_KEY:
            if v != command.value:
                raise Exception(
                    f"Command '{command.value}' does not match value of which: '{v}'"
                )
            continue

        # param was assigned from defaults and should not be included
        if k not in (cmd_args | prnt_args) or (
            k in default_args and v == FLAGS_DEFAULTS[k.upper()]
        ):
            continue

        # if the param is in parent args, it should come before the arg name
        # e.g. ["--print", "run"] vs ["run", "--print"]
        add_fn = res.append
        # if k in prnt_args:

        #     def add_fn(x):
        #         res.insert(0, x)

        spinal_cased = k.replace("_", "-")

        # MultiOption flags come back as lists, but we want to pass them as space separated strings
        if isinstance(v, list):
            if len(v) > 0:
                v = " ".join(v)
            else:
                continue

        if k == "macro" and command == CliCommand.RUN_OPERATION:  # type: ignore
            add_fn(v)
        # None is a Singleton, False is a Flyweight, only one instance of each.
        elif (v is None or v is False) and k not in (
            # These are None by default but they do not support --no-{flag}
            "defer_state",
            "log_format",
        ):
            add_fn(f"--no-{spinal_cased}")
        elif v is True:
            add_fn(f"--{spinal_cased}")
        else:
            add_fn(f"--{spinal_cased}={v}")

    return res


ArgsList = List[str]


def parent_args() -> ArgsList:
    """Return a list representing the params the base click command takes."""
    from morph.cli.main import cli  # type: ignore

    return format_params(cli.params)


def command_args(command: CliCommand) -> ArgsList:
    """Given a command, return a list of strings representing the params
    that command takes. This function only returns params assigned to a
    specific command, not those of its parent command.

    e.g. fn("run") -> ["defer", "favor_state", "exclude", ...]
    """
    import morph.cli.main as cli

    CMD_DICT: Dict[CliCommand, ClickCommand] = {
        CliCommand.INIT: cli.init,  # type: ignore
        CliCommand.RUN: cli.run,  # type: ignore
    }
    click_cmd: Optional[ClickCommand] = CMD_DICT.get(command, None)
    if click_cmd is None:
        raise Exception(f"No command found for name '{command.name}'")
    return format_params(click_cmd.params)


def format_params(params: List[Parameter]) -> ArgsList:
    return [
        str(x.name) for x in params if not str(x.name).lower().startswith("deprecated_")
    ]


def get_latest_version() -> Optional[str]:
    """Retrieve the latest morph-data version from PyPI."""
    try:
        response = requests.get("https://pypi.org/pypi/morph-data/json", timeout=5)
        if response.status_code == 200:
            json_data: Any = response.json()
            info = json_data.get("info", {})
            version = info.get("version")
            if isinstance(version, str):
                return version
        return None
    except Exception as e:  # noqa
        click.echo(
            click.style(f"Warning: Failed to check latest version: {e}", fg="yellow")
        )
        return None


def check_version_warning():
    """Check if the current version is outdated and display a warning if necessary."""
    try:
        # Get the current version of morph-data
        current_version_str = importlib.metadata.version("morph-data")
        try:
            current_version = Version(current_version_str)
        except InvalidVersion:
            click.echo(
                click.style(
                    f"Warning: Current version {current_version_str} is not a valid semantic version.",
                    fg="yellow",
                )
            )
            return

        # Get the latest version of morph-data from PyPI
        latest_version_str = get_latest_version()
        if latest_version_str:
            try:
                latest_version = Version(latest_version_str)
            except InvalidVersion:
                click.echo(
                    click.style(
                        f"Warning: Latest version {latest_version_str} is not a valid semantic version.",
                        fg="yellow",
                    )
                )
                return

            # Compare versions
            if current_version < latest_version:
                click.echo()
                click.echo(
                    click.style(
                        f"You are using morph-data version {current_version}; however, version {latest_version} is available.\n"
                        "You should consider upgrading via the 'pip install --upgrade morph-data' command.",
                        fg="yellow",
                    )
                )
                click.echo()
    except importlib.metadata.PackageNotFoundError:
        click.echo(click.style("Warning: morph-data is not installed.", fg="red"))
    except Exception as e:
        click.echo(click.style(f"Warning: Failed to check version: {e}", fg="yellow"))
