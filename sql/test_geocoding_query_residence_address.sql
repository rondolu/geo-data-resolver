-- ============================================================
-- 舊版測試資料 - residence_address (2筆不符合 API request 要求)
-- 目的：驗證地址 geocoding call 後的錯誤回應（例如 ZERO_RESULTS / INVALID_REQUEST）
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
--     "TEST_ERR_RESIDENCE_0001" AS serial_number,
--     "2026-04-10 09:10:00+00" AS created_at,
--     "cuid-test-residence-0001" AS cuid,
--     "!@#$%^^^&&&&^%$" AS request_address,
--     CAST(NULL AS FLOAT64) AS request_longitude,
--     CAST(NULL AS FLOAT64) AS request_latitude
--   UNION ALL
--   SELECT
--     "TEST_ERR_RESIDENCE_0002" AS serial_number,
--     "2026-04-10 09:11:00+00" AS created_at,
--     "cuid-test-residence-0002" AS cuid,
--     "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz" AS request_address,
--     CAST(NULL AS FLOAT64) AS request_longitude,
--     CAST(NULL AS FLOAT64) AS request_latitude
-- ) AS test_data
-- WHERE NOT EXISTS (
--   SELECT 1
--   FROM `RAW_EDEP_DATASET.GEOCODING` g
--   WHERE g.SERIAL_NUMBER = test_data.serial_number
-- )
-- ORDER BY serial_number

-- ============================================================
-- 測試發查名單 - residence_address (5筆符合 API request 要求) (2026-04-10)
-- 目的：驗證地址 geocoding call 後能如預期回報對應的回應結果
-- ============================================================

SELECT
  serial_number,
  created_at,
  partition_date,
  cuid,
  request_address,
  request_longitude,
  request_latitude
FROM (
  SELECT
    "TEST_RESIDENCE_0001" AS serial_number,
    "2026-04-10 09:10:00+00" AS created_at,
    DATE "2026-04-10" AS partition_date,
    "cuid-test-residence-0001" AS cuid,
    "Ấp 2A Tân Hòa" AS request_address,
    CAST(NULL AS FLOAT64) AS request_longitude,
    CAST(NULL AS FLOAT64) AS request_latitude
  UNION ALL
  SELECT
    "TEST_RESIDENCE_0002" AS serial_number,
    "2026-04-10 09:11:00+00" AS created_at,
    DATE "2026-04-10" AS partition_date,
    "cuid-test-residence-0002" AS cuid,
    "22 Trần Hưng Đạo, Phường 2, Sóc Trăng" AS request_address,
    CAST(NULL AS FLOAT64) AS request_longitude,
    CAST(NULL AS FLOAT64) AS request_latitude
  UNION ALL
  SELECT
    "TEST_RESIDENCE_0003" AS serial_number,
    "2026-04-10 09:12:00+00" AS created_at,
    DATE "2026-04-10" AS partition_date,
    "cuid-test-residence-0003" AS cuid,
    "Số 55/46 Tôn Đức Thắng Khóm 5, Phường 6, TP. Sóc Trăng, Sóc Trăng" AS request_address,
    CAST(NULL AS FLOAT64) AS request_longitude,
    CAST(NULL AS FLOAT64) AS request_latitude
  UNION ALL
  SELECT
    "TEST_RESIDENCE_0004" AS serial_number,
    "2026-04-10 09:13:00+00" AS created_at,
    DATE "2026-04-10" AS partition_date,
    "cuid-test-residence-0004" AS cuid,
    "XÃ THĂNG LONG 778" AS request_address,
    CAST(NULL AS FLOAT64) AS request_longitude,
    CAST(NULL AS FLOAT64) AS request_latitude
  UNION ALL
  SELECT
    "TEST_RESIDENCE_0005" AS serial_number,
    "2026-04-10 09:14:00+00" AS created_at,
    DATE "2026-04-10" AS partition_date,
    "cuid-test-residence-0005" AS cuid,
    "Tổ 5 Khu 10, Nông Trang, 227, 25" AS request_address,
    CAST(NULL AS FLOAT64) AS request_longitude,
    CAST(NULL AS FLOAT64) AS request_latitude
) AS test_data
WHERE NOT EXISTS (
  SELECT 1
  FROM `RAW_EDEP_DATASET.GEOCODING` g
  WHERE g.SERIAL_NUMBER = test_data.serial_number
)
ORDER BY serial_number
LIMIT 3