import pandas as pd

import morph
from morph import MorphGlobalContext


# Morph decorators
# The `@morph.func` decorator required to be recognized as a function in morph.
# For more information: https://docs.morph-data.io
@morph.func(
    name="starter_function",
)
def starter_function(context: MorphGlobalContext) -> pd.DataFrame:
    return pd.DataFrame({{"key1": [1, 2, 3], "key2": [3, 4, 5]}})
