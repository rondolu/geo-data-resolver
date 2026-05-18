-- 參照 SASD 附錄四：更新已發查通訊地址
INSERT INTO `RAW_EDEP_DATASET.GEOCODING` (
  PARTITION_DATE,
  CUID,
  SERIAL_NUMBER,
  CREATED_AT,
  GEO_TYPE,
  REQUEST_ADDRESS,
  RESPONSE_PLACE_ID,
  RESPONSE_ADDRESS,
  RESPONSE_GLOBAL_CODE,
  RESPONSE_PLACE_TYPES,
  RESPONSE_LONGITUDE,
  RESPONSE_LATITUDE,
  RESPONSE_COUNTRY,
  RESPONSE_CITY,
  RESPONSE_DISTRICT,
  RESPONSE_WARD,
  RESPONSE_STREET,
  BQ_CREATED_TIME,
  BQ_UPDATED_TIME
)
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
    current_detailed_address
  FROM `RAW_HES_DATASET.CUSTOMER`
  WHERE UPPER(COALESCE(current_detailed_address, 'NULL')) != 'NULL'
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY cuid
    ORDER BY BQ_UPDATED_TIME DESC
  ) = 1
),
geocoding_serial_number_list AS (
  SELECT DISTINCT serial_number
  FROM `RAW_EDEP_DATASET.GEOCODING`
  WHERE GEO_TYPE = 'CONTACT_ADDRESS'
),
distinct_address AS (
  SELECT DISTINCT
    REQUEST_ADDRESS,
    RESPONSE_PLACE_ID,
    RESPONSE_ADDRESS,
    RESPONSE_GLOBAL_CODE,
    RESPONSE_PLACE_TYPES,
    RESPONSE_LONGITUDE,
    RESPONSE_LATITUDE,
    RESPONSE_COUNTRY,
    RESPONSE_CITY,
    RESPONSE_DISTRICT,
    RESPONSE_WARD,
    RESPONSE_STREET
  FROM `RAW_EDEP_DATASET.GEOCODING`
  WHERE GEO_TYPE = 'CONTACT_ADDRESS'
    AND UPPER(COALESCE(RESPONSE_ADDRESS, 'NULL')) != 'NULL'
)
SELECT
  CURRENT_DATE(),
  cust.cuid,
  appl.serial_number,
  appl.created_at,
  'CONTACT_ADDRESS',
  cust.current_detailed_address,
  geo_coding.RESPONSE_PLACE_ID,
  geo_coding.RESPONSE_ADDRESS,
  geo_coding.RESPONSE_GLOBAL_CODE,
  geo_coding.RESPONSE_PLACE_TYPES,
  geo_coding.RESPONSE_LONGITUDE,
  geo_coding.RESPONSE_LATITUDE,
  geo_coding.RESPONSE_COUNTRY,
  geo_coding.RESPONSE_CITY,
  geo_coding.RESPONSE_DISTRICT,
  geo_coding.RESPONSE_WARD,
  geo_coding.RESPONSE_STREET,
  DATETIME(SAFE_CAST(appl.created_at AS TIMESTAMP), 'UTC'),
  CURRENT_DATETIME('UTC')
FROM latest_hes_application AS appl
JOIN latest_hes_customer AS cust
  ON appl.customer_id = cust.id
  AND appl.id = cust.current_application_id
LEFT JOIN geocoding_serial_number_list AS ser_list
  ON appl.serial_number = ser_list.serial_number
LEFT JOIN distinct_address AS geo_coding
  ON cust.current_detailed_address = geo_coding.REQUEST_ADDRESS
WHERE ser_list.serial_number IS NULL
  AND geo_coding.REQUEST_ADDRESS IS NOT NULL