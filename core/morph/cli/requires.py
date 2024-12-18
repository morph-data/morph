from functools import update_wrapper

from click import Context

from morph.cli.flags import Flags, set_flags


def preflight(func):
    def wrapper(*args, **kwargs):
        ctx = args[0]
        assert isinstance(ctx, Context)
        ctx.obj = ctx.obj or {}

        # Flags
        flags = Flags(ctx)
        ctx.obj["flags"] = flags
        set_flags(flags)

        return func(*args, **kwargs)

    return update_wrapper(wrapper, func)


def postflight(func):
    def wrapper(*args, **kwargs):
        # ctx = args[0]
        success = False

        try:
            result, success = func(*args, **kwargs)
        except Exception as e:
            raise e
        finally:
            pass
        return (result, success)

    return update_wrapper(wrapper, func)
