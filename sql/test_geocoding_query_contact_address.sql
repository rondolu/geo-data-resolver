-- ============================================================
-- 舊版測試資料 - contact_address (2筆不符合 API request 要求)
-- 目的：驗證地址 geocoding call 後的錯誤回應（例如 ZERO_RESULTS）
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
--     "TEST_ERR_CONTACT_0001" AS serial_number,
--     "2026-04-10 09:00:00+00" AS created_at,
--     "cuid-test-contact-0001" AS cuid,
--     "" AS request_address,
--     CAST(NULL AS FLOAT64) AS request_longitude,
--     CAST(NULL AS FLOAT64) AS request_latitude
--   UNION ALL
--   SELECT
--     "TEST_ERR_CONTACT_0002" AS serial_number,
--     "2026-04-10 09:01:00+00" AS created_at,
--     "cuid-test-contact-0002" AS cuid,
--     null AS request_address,
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
-- 測試發查名單 - contact_address (5筆符合 API request 要求) (2026-04-10)
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
    "TEST_CONTACT_0001" AS serial_number,
    "2026-04-10 09:00:00+00" AS created_at,
    DATE "2026-04-10" AS partition_date,
    "cuid-test-contact-0001" AS cuid,
    "Buôn Ciet, Ea Tiêu" AS request_address,
    CAST(NULL AS FLOAT64) AS request_longitude,
    CAST(NULL AS FLOAT64) AS request_latitude
  UNION ALL
  SELECT
    "TEST_CONTACT_0002" AS serial_number,
    "2026-04-10 09:01:00+00" AS created_at,
    DATE "2026-04-10" AS partition_date,
    "cuid-test-contact-0002" AS cuid,
    "XÃ THĂNG LONG" AS request_address,
    CAST(NULL AS FLOAT64) AS request_longitude,
    CAST(NULL AS FLOAT64) AS request_latitude
  UNION ALL
  SELECT
    "TEST_CONTACT_0003" AS serial_number,
    "2026-04-10 09:02:00+00" AS created_at,
    DATE "2026-04-10" AS partition_date,
    "cuid-test-contact-0003" AS cuid,
    "428/14 Luỹ Bán BíchHòa Thạnh" AS request_address,
    CAST(NULL AS FLOAT64) AS request_longitude,
    CAST(NULL AS FLOAT64) AS request_latitude
  UNION ALL
  SELECT
    "TEST_CONTACT_0004" AS serial_number,
    "2026-04-10 09:03:00+00" AS created_at,
    DATE "2026-04-10" AS partition_date,
    "cuid-test-contact-0004" AS cuid,
    "Tổ 08, Nam Giang, Nam Trực, Nam Định" AS request_address,
    CAST(NULL AS FLOAT64) AS request_longitude,
    CAST(NULL AS FLOAT64) AS request_latitude
  UNION ALL
  SELECT
    "TEST_CONTACT_0005" AS serial_number,
    "2026-04-10 09:04:00+00" AS created_at,
    DATE "2026-04-10" AS partition_date,
    "cuid-test-contact-0005" AS cuid,
    "THÔN 3, XÃ LỘC AN" AS request_address,
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