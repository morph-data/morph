import plotly.express as px

import morph
from morph import MorphGlobalContext


@morph.func
@morph.load_data("example_data")
def example_chart(context: MorphGlobalContext):
    df = context.data["example_data"].groupby("state").sum(["population"]).reset_index()
    fig = px.bar(df, x="state", y="population")
    return fig
