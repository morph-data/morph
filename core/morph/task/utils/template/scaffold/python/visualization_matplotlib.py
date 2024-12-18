import matplotlib.pyplot as plt

import morph
from morph import MorphGlobalContext


# Morph decorators
# The `@morph.func` decorator required to be recognized as a function in morph.
# The `@morph.load_data` decorator required to load data from parent file or function.
#   - The parent is executed before the current function and the data is passed to the current function as `context.data``.
# For more information: https://docs.morph-data.io
@morph.func(
    name="visualize_matplotlib",
)
@morph.load_data("{MORPH_PARENT_NAME}")
def visualize_matplotlib(context: MorphGlobalContext) -> plt.Figure:
    data = context.data["{MORPH_PARENT_NAME}"]
    # This is where you write your code.
    # The `plot` function creates a line plot using Matplotlib.
    fig, ax = plt.subplots()
    ax.plot(data["X-Axis"], data["Y-Axis"], marker="o")
    ax.set_title("Matplotlib Plot")
    ax.set_xlabel("X-Axis")
    ax.set_ylabel("Y-Axis")
    return fig
