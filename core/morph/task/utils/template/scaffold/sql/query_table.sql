-- Morph SQL configuration
-- For more information: https://docs.morph-data.io
{{
	config(
		name="query_table",
		description="Query from {TABLE_NAME} table",
        connection=None,
	)
}}

SELECT * FROM {TABLE_NAME} LIMIT 50
