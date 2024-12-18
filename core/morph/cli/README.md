# Adding a new command

## `main.py`

Add the new command with all necessary decorators. Every command will need at minimum:

- a decorator for the click group it belongs to which also names the command
- the postflight decorator (must come before other decorators from the requires module for error handling)
- the preflight decorator

```python
@cli.command("my-new-command")
@requires.postflight
@requires.preflight
def my_new_command(ctx, **kwargs):
    ...
```

# Exception Handling

## `requires.py`

### `postflight`
