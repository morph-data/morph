-- Morph SQL configuration
-- For more information: https://docs.morph-data.io
{{
	config(
		name="count_records_by_field_name",
		description="count records from ${TABLE_NAME} by {GROUP_FIELD}",
        connection=None,
	)
}}

SELECT {GROUP_FIELD}, COUNT(*) AS CountPerGroup
FROM {TABLE_NAME}
GROUP BY {GROUP_FIELD}
