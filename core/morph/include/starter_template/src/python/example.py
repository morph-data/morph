import pandas as pd
import plotly.express as px

import morph
from morph import MorphGlobalContext


@morph.func
@morph.load_data("example_data")
def example_chart(context: MorphGlobalContext):
    df = context.data["example_data"]

    chart_type = context.vars["chartType"]
    if chart_type == "line":
        fig = px.line(df, x="data", y=["traffic", "orders"], color="source")
    elif chart_type == "stacked":
        fig = px.bar(df, x="data", y="traffic", color="source", barmode="stack")
    elif chart_type == "area":
        fig = px.area(df, x="data", y="traffic", color="source")
    return fig


@morph.func
@morph.load_data("example_data")
def example_metrics(context: MorphGlobalContext):
    df = context.data["example_data"]

    # Get the latest date
    latest_date = df["data"].max()
    latest_df = df[df["data"] == latest_date]

    # Get the best campaign in the latest month
    best_campaign = latest_df.loc[latest_df["orders"].idxmax(), "source"]

    # Get the total orders and traffic in the latest month
    total_orders = latest_df["orders"].sum()
    total_traffic = latest_df["traffic"].sum()

    result_df = pd.DataFrame(
        [
            {"label": "Latest Date", "value": latest_date.strftime("%Y-%m-%d")},
            {"label": "Best Campaign", "value": best_campaign},
            {"label": "Total Orders", "value": f"{total_orders:,}"},
            {"label": "Total Traffic", "value": f"{total_traffic:,}"},
        ]
    )

    return result_df
