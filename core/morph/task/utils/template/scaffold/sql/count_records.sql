-- Morph SQL configuration
-- For more information: https://docs.morph-data.io
{{
	config(
		name="count_records",
		description="Count records from {TABLE_NAME} table",
        connection=None,
	)
}}

SELECT COUNT(*) AS TotalRecords
FROM {TABLE_NAME}
