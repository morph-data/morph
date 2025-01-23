{{
    config(
        name = "example_data",
        connection = "DUCKDB"
    )
}}

select
    *
from
    read_csv("src/example.csv")
