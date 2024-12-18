-- Morph SQL configuration
-- For more information: https://docs.morph-data.io
{{
	config(
		name="calc_sum_field_name",
		description="calculate the sum of {FIELD_NAME}",
        connection=None,
	)
}}

SELECT SUM({FIELD_NAME}) AS TotalSum
FROM {TABLE_NAME}
