-- Morph SQL configuration
-- For more information: https://docs.morph-data.io
{{
	config(
		name="calc_sum_more_than_100",
		description="Calculate the sum of {GROUP_FIELD} more than 100",
        connection=None,
	)
}}

SELECT {GROUP_FIELD}, SUM({FIELD_NAME}) AS GroupTotal
FROM {TABLE_NAME}
GROUP BY {GROUP_FIELD}
HAVING SUM({FIELD_NAME}) > 100
