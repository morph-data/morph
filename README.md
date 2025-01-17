![Header](https://data.morphdb.io/assets/header.jpg)

## Features

[Morph](https://www.morph-data.io/) is a python-centric full-stack framework for building and deploying data apps.

- **Fast to start** 🚀 - Allows you to get up and running with just three commands.
- **Deploy and operate 🌐** - Easily deploy your data apps and manage them in production. Managed cloud is available for user authentication and secure data connection.
- **No HTML/CSS knowledge required🔰** - With **Markdown-based syntax** and **pre-made components**, you can create flexible, visually appealing designs without writing a single line of HTML or CSS.
- **Customizable 🛠️** - **Chain Python and SQL** for advanced data workflows. Custom CSS and custom React components are available for building tailored UI.

## Quick start

1. Install morph

```bash
pip install morph-data
```

2. Create a new project

```bash
morph new
```

3. Start dev server

```bash
morph serve
```

4. Visit `http://localhsot:8080` on browser.

## How it works

Understanding the concept of developing a data app in Morph will let you do a flying start.

1. Develop the data processing in Python and give it an alias.
2. Create an .mdx file. Each .mdx file becomes a page of your app.
3. Place the component in the MDX file and specify the alias to connect to.

```
.
├─ pages
│  └─ index.mdx
├─ python
│  └─ closing_deals_vis.py
└─ sql
   └─ closing_deals.sql
```

## Building Data Apps

### A little example

1. Create each files in `sql`, `python` and `pages` directories.

SQL: Using DuckDB to read CSV file.

```sql
{{
    config(
        name = "example_data",
        connection = "DUCKDB"
    )
}}

select
    *
from
    read_csv("example.csv")
```

Python: Using Plotly to create a chart.

```python
import plotly.express as px
import morph
from morph import MorphGlobalContext
@morph.func
@morph.load_data("example_data")
def example_chart(context: MorphGlobalContext):
    df = context.data["example_data"].groupby("state").sum(["population"]).reset_index()
    fig = px.bar(df, x="state", y="population")
    return fig
```

MDX: Define the page and connect the data.

```typescript
export const title = "Starter App"

# Starter App

Morph is a full-stack framework for building data apps using Python, SQL and MDX.

## Data

<Grid cols="2">
  <div>
    <DataTable loadData="example_data" height={300} />
  </div>
  <div>
    <Embed loadData="example_chart" height={300} />
  </div>
</Grid>
```

2. Run `morph serve` to open the app!

![Data App](https://data.morphdb.io/assets/sample-data-app.png)

## Documentation

Visit https://docs.morph-data.io for more documentation.

## Contributing

Thanks for your interest in helping improve Morph ❤️

- Before contributing, please read the [CONTRIBUTING.md](CONTRIBUTING.md).
- If you find any issues, please let us know and open [an issue](https://github.com/morph-data/morph/issues/new/choose).

## Lisence

Morph is [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) licensed.
