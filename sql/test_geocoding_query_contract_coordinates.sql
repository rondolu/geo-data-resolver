-- ============================================================
-- 舊版測試資料 - contract_coordinates (2筆不符合 API request 要求)
-- 目的：驗證 reverse geocoding call 後的錯誤回應（例如 INVALID_REQUEST）
-- ============================================================
-- SELECT
--   serial_number,
--   created_at,
--   cuid,
--   request_address,
--   request_longitude,
--   request_latitude
-- FROM (
--   SELECT
--     "TEST_ERR_COORD_0001" AS serial_number,
--     "2026-04-10 09:20:00+00" AS created_at,
--     "cuid-test-coord-0001" AS cuid,
--     CAST(NULL AS STRING) AS request_address,
--     null AS request_longitude,
--     null AS request_latitude
--   UNION ALL
--   SELECT
--     "TEST_ERR_COORD_0002" AS serial_number,
--     "2026-04-10 09:21:00+00" AS created_at,
--     "cuid-test-coord-0002" AS cuid,
--     CAST(NULL AS STRING) AS request_address,
--     "abc" AS request_longitude,
--     "def" AS request_latitude
-- ) AS test_data
-- WHERE NOT EXISTS (
--   SELECT 1
--   FROM `RAW_EDEP_DATASET.GEOCODING` g
--   WHERE g.SERIAL_NUMBER = test_data.serial_number
-- )
-- ORDER BY serial_number

-- ============================================================
-- 測試發查名單 - contract_coordinates (5筆符合 API request 要求) (2026-04-10)
-- 目的：驗證座標 reverse geocoding call 後能如預期回報對應的回應結果
-- ============================================================

SELECT
  serial_number,
  created_at,
  partition_date,
  cuid,
  -- request_address,
  request_longitude,
  request_latitude
FROM (
  SELECT
    "TEST_COORD_20260517_0001" AS serial_number,
    "2026-05-17 09:20:00+00" AS created_at,
    DATE "2026-05-17" AS partition_date,
    "cuid-test-coord-20260517_0001" AS cuid,
    "107.1833992" AS request_longitude,
    "10.4966813" AS request_latitude
  UNION ALL
  SELECT
    "TEST_COORD_2026050517_0002" AS serial_number,
    "2026-05-17 09:21:00+00" AS created_at,
    DATE "2026-05-17" AS partition_date,
    "cuid-test-coord-20260517_0002" AS cuid,
    "105.9323115" AS request_longitude,
    "10.1740503" AS request_latitude
  -- UNION ALL
  -- SELECT
  --   "TEST_COORD_0003" AS serial_number,
  --   "2026-04-10 09:22:00+00" AS created_at,
  --   DATE "2026-04-10" AS partition_date,
  --   "cuid-test-coord-0003" AS cuid,
  --   CAST(NULL AS STRING) AS request_address,
  --   "108.176" AS request_longitude,
  --   "16.0724" AS request_latitude
  -- UNION ALL
  -- SELECT
  --   "TEST_COORD_0004" AS serial_number,
  --   "2026-04-10 09:23:00+00" AS created_at,
  --   DATE "2026-04-10" AS partition_date,
  --   "cuid-test-coord-0004" AS cuid,
  --   CAST(NULL AS STRING) AS request_address,
  --   "106.6776" AS request_longitude,
  --   "10.746" AS request_latitude
  -- UNION ALL
  -- SELECT
  --   "TEST_COORD_0005" AS serial_number,
  --   "2026-04-10 09:24:00+00" AS created_at,
  --   DATE "2026-04-10" AS partition_date,
  --   "cuid-test-coord-0005" AS cuid,
  --   CAST(NULL AS STRING) AS request_address,
  --   "105.9318" AS request_longitude,
  --   "10.1726" AS request_latitude
) AS test_data
WHERE NOT EXISTS (
  SELECT 1
  FROM `RAW_EDEP_DATASET.GEOCODING` g
  WHERE g.SERIAL_NUMBER = test_data.serial_number
)
ORDER BY serial_number
LIMIT 3