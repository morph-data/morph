from typing import Dict

import pandas as pd
from morph_lib.database import execute_sql

import morph
from morph import MorphGlobalContext


# Morph decorators
# The `@morph.func` decorator required to be recognized as a function in morph.
# For more information: https://docs.morph-data.io
@morph.func(
    name="execute_sql",
)
def get_sql_result(context: MorphGlobalContext) -> pd.DataFrame:
    # This is where you write your code.
    # The `execute_sql` function executes the specified SQL query and returns the result as a pandas dataframe.
    data: Dict[str, pd.DataFrame] = {"sql_result": execute_sql("SELECT 1 as test")}
    return pd.DataFrame(data["sql_result"])
