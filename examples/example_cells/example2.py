import pandas as pd

import morph
from morph import MorphGlobalContext


@morph.func(name="alias2")
def main(context: MorphGlobalContext):
    return pd.DataFrame(
        {
            "name": ["Alice", "Bob", "Charlie"],
            "branch": ["A", "B", "C"],
            "score": [85, 90, 95],
        }
    )
