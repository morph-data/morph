import plotly.express as px

import morph
from morph import MorphGlobalContext


# Morph decorators
# The `@morph.func` decorator required to be recognized as a function in morph.
# The `@morph.load_data` decorator required to load data from parent file or function.
#   - The parent is executed before the current function and the data is passed to the current function as `context.data``.
# For more information: https://docs.morph-data.io
@morph.func(
    name="visualize_plotly",
)
@morph.load_data("{MORPH_PARENT_NAME}")
def visualize_plotly(context: MorphGlobalContext) -> px.line:
    data = context.data["{MORPH_PARENT_NAME}"]
    # This is where you write your code.
    # The `px.line` function creates a line plot using Plotly Express.
    # The `update_layout` function updates the layout of the plot.
    fig = px.line(data, x="X Axis", y="Y Axis", markers=True)
    fig.update_layout(title="Plotly Plot")
    return fig
