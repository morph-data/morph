import pandas as pd

import morph
from morph import MorphGlobalContext


# Morph decorators
# The `@morph.func` decorator required to be recognized as a function in morph.
# The `@morph.load_data` decorator required to load data from parent file or function.
#   - The parent is executed before the current function and the data is passed to the current function as `context.data``.
# For more information: https://docs.morph-data.io
@morph.func(
    name="load_data_from_result",
)
# morph.load_data is a decorator that takes in the following parameters:
# {MORPH_PARENT_NAME}: The alias of another parent file. The function will be executed before the main function.
@morph.load_data("{MORPH_PARENT_NAME}")
def load_data_from_result(context: MorphGlobalContext) -> pd.DataFrame:
    # This is where you write your code.
    data = context.data["{MORPH_PARENT_NAME}"]
    return pd.DataFrame(data)
