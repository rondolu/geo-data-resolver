WITH latest_hes_application AS (
  SELECT
    id,
    serial_number,
    created_at,
    PARTITION_DATE AS partition_date,
    customer_id,
    BQ_UPDATED_TIME
  FROM `RAW_HES_DATASET.APPLICATION`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY id
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
latest_hes_customer AS (
  SELECT
    id,
    cuid,
    current_application_id,
    permanent_detailed_address
  FROM `RAW_HES_DATASET.CUSTOMER`
  WHERE UPPER(COALESCE(permanent_detailed_address, 'NULL')) != 'NULL'
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cuid
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
)
SELECT
  appl.serial_number,
  appl.created_at,
  appl.partition_date,
  cust.cuid,
  cust.permanent_detailed_address AS request_address,
  CAST(NULL AS FLOAT64) AS request_longitude,
  CAST(NULL AS FLOAT64) AS request_latitude
FROM latest_hes_application AS appl
JOIN latest_hes_customer AS cust
  ON appl.customer_id = cust.id
  AND appl.id = cust.current_application_id
WHERE NOT EXISTS (
  SELECT 1
  FROM `RAW_EDEP_DATASET.GEOCODING` AS geo_coding
  WHERE geo_coding.GEO_TYPE = 'RESIDENCE_ADDRESS'
    AND geo_coding.SERIAL_NUMBER = appl.serial_number
)
  AND NOT EXISTS (
    SELECT 1
    FROM `RAW_EDEP_DATASET.GEOCODING` AS geo_coding
    WHERE geo_coding.GEO_TYPE = 'RESIDENCE_ADDRESS'
      AND UPPER(COALESCE(geo_coding.REQUEST_ADDRESS, 'NULL')) != 'NULL'
      AND geo_coding.REQUEST_ADDRESS = cust.permanent_detailed_address
  )
ORDER BY serial_number DESC
LIMIT 500