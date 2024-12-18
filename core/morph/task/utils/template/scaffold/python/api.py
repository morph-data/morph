import morph
from morph import MorphGlobalContext


# Morph decorators
# The `@morph.func` decorator required to be recognized as a function in morph.
# For more information: https://docs.morph-data.io
@morph.func(
    name="get_json_result",
)
def get_json_result(context: MorphGlobalContext) -> dict:
    # This is where you write your code.
    # should return a dictionary
    return {"message": "ok"}
