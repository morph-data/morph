{{
    config(
        name = "example_data",
        connection = "DUCKDB"
    )
}}

select
    *
from
    read_csv("data/example.csv")
