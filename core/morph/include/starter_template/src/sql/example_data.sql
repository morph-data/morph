{{
    config(
        name = "example_data",
        connection = "DUCKDB"
    )
}}

select
    Date as data,
    Source as source,
    Traffic as traffic,
    Orders as orders
from
    read_csv("./data/Traffic_Orders_Demo_Data.csv")
where
    Date >= '2023-01-01'
