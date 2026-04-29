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
    cuid
  FROM `RAW_HES_DATASET.CUSTOMER`
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cuid
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
latest_vmb_apply_info AS (
  SELECT
    cuid,
    ROUND(SAFE_CAST(longitude AS FLOAT64), 4) AS longitude,
    ROUND(SAFE_CAST(latitude AS FLOAT64), 4) AS latitude
  FROM `RAW_VMB_DATASET.APPLY_INFO`
  WHERE UPPER(COALESCE(longitude, 'NULL')) != 'NULL'
    AND UPPER(COALESCE(latitude, 'NULL')) != 'NULL'
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
  CAST(NULL AS STRING) AS request_address,
  CAST(apply_info.longitude AS STRING) AS request_longitude,
  CAST(apply_info.latitude AS STRING) AS request_latitude
FROM latest_hes_application AS appl
JOIN latest_hes_customer AS cust
  ON appl.customer_id = cust.id
JOIN latest_vmb_apply_info AS apply_info
  ON cust.cuid = apply_info.cuid
WHERE NOT EXISTS (
  SELECT 1
  FROM `RAW_EDEP_DATASET.GEOCODING` AS geo_coding
  WHERE geo_coding.GEO_TYPE = 'CONTRACT_COORDINATES'
    AND geo_coding.SERIAL_NUMBER = appl.serial_number
)
  AND NOT EXISTS (
    SELECT 1
    FROM `RAW_EDEP_DATASET.GEOCODING` AS geo_coding
    WHERE geo_coding.GEO_TYPE = 'CONTRACT_COORDINATES'
      AND SAFE_CAST(geo_coding.REQUEST_LONGITUDE AS FLOAT64) IS NOT NULL
      AND SAFE_CAST(geo_coding.REQUEST_LATITUDE AS FLOAT64) IS NOT NULL
      AND SAFE_CAST(geo_coding.REQUEST_LONGITUDE AS FLOAT64) = apply_info.longitude
      AND SAFE_CAST(geo_coding.REQUEST_LATITUDE AS FLOAT64) = apply_info.latitude
  )
ORDER BY serial_number DESC
LIMIT 500