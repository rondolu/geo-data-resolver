---
goal: Geocoding Response Alignment Implementation Plan
version: 1.0
date_created: 2026-05-15
last_updated: 2026-05-15
owner: GitHub Copilot
status: Planned
tags: [feature, geocoding, sql, documentation, bugfix]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

本計畫定義 `geo-data-resolver` 專案中 Geocoding API request、response 解析、GCS 原始資料儲存、SQL 邏輯與 SASD 文件同步調整的最小改動方案。目標是讓既有 `contact_address`、`residence_address`、`contract_coordinates` 流程符合新版 Google Maps Geocoding response 結構與最新業務規則，且不擴大變更到本需求以外的模組。

## 1. Requirements & Constraints

- **REQ-001**: 在 `infrastructure/google_maps_client.py` 的 `GoogleMapsAPIClient.get_geocoding` 中，所有 Geocoding GET request 必須固定加入 query parameter `fulfill_on_zero_results=true`。
- **REQ-002**: 在 `application/geocoding_batch_process_service.py` 的 `GeocodingBatchProcessService._build_bq_row` 中，`RESPONSE_GLOBAL_CODE` 必須優先取 root-level `plus_code.global_code`。
- **REQ-003**: 當 root-level `plus_code.global_code` 無值時，`RESPONSE_GLOBAL_CODE` 必須 fallback 至 `results[0].plus_code.global_code`，且當 `results` 為空時不可拋出未處理錯誤。
- **REQ-004**: 在 `application/geocoding_batch_process_service.py` 的 `GeocodingBatchProcessService._process_batch_records` 中，寫入 BigQuery 的成功結果仍可使用 `api_response["results"][0]` 作為地址欄位來源，但 GCS 儲存內容必須保留完整 root-level response。
- **REQ-005**: 在 `application/geocoding_batch_process_service.py` 的 `GeocodingBatchProcessService._upload_success_rows_to_gcs` 中，GCS payload 必須直接序列化完整 `api_response`，不可裁切成單一 result。
- **REQ-006**: 在 `sql/geocoding_query_contract_coordinates.sql` 中，`RAW_VMB_DATASET.APPLY_INFO.longitude` 與 `latitude` 必須改為原始精度，不再使用 `ROUND(..., 4)`。
- **REQ-007**: 在 `sql/geocoding_query_contract_coordinates.sql` 中，`RAW_HES_DATASET.APPLICATION` 查詢必須新增 `status = "ACTIVE"` 篩選條件。
- **REQ-008**: 在 `application/geocoding_batch_process_service.py` 的 `GeocodingBatchProcessService._call_geocoding_api` 中，contract coordinates 的 `latlng` 組裝必須保留來源字串原始精度，不可額外格式化為四位小數。
- **REQ-009**: 在 `sql/geocoding_query_contact_address.sql` 與 `sql/geocoding_query_residence_address.sql` 中，`latest_hes_application` 與 `latest_hes_customer` 的 join 條件必須同時包含 `appl.customer_id = cust.id` 以及 `appl.id = cust.current_application_id`。
- **REQ-010**: 第 9 點 join 條件調整不得套用到 `sql/geocoding_query_contract_coordinates.sql`。
- **REQ-011**: 在 `sql/geocoding_update_contact_address.sql` 與 `sql/geocoding_update_residence_address.sql` 中，`INSERT ... SELECT` 寫入的 `PARTITION_DATE` 必須改為 `CURRENT_DATE()`。
- **REQ-012**: 第 11 點 `PARTITION_DATE` 調整不得套用到 contract coordinates update SQL。
- **REQ-013**: `sql/geocoding_update_contract_coordinates.sql` 必須整份以 SQL 註解方式停用，檔案需保留內容但不可執行。
- **REQ-014**: `docs/SASD_GoogleMaps_Geocoding.md` 中 Geocoding response 範例、欄位說明與描述文字必須更新為 root-level `plus_code` 與 `results` 並存的新結構。
- **REQ-015**: 文件中 `RESPONSE_GLOBAL_CODE` 對應說明必須明確記載 root-level `plus_code.global_code` 優先，無值時 fallback 至 `results[0].plus_code.global_code`。
- **REQ-016**: 需納入 ALT-001：在 `models/geocoding_models.py` 新增 root-level `plus_code` 的 Pydantic schema，並將 response mapping 轉為由模型輸出統一欄位，避免 service 層手動拆解 root/result。
- **SEC-001**: 不可新增硬編碼 API key；既有 Secret Manager 讀取路徑必須維持不變。
- **CON-001**: 採最小改動原則；不得重構 `GeocodingBatchProcessService`、`GoogleMapsAPIClient` 或 BigQuery/GCS 公用服務的整體架構。
- **CON-002**: 不可變更非 address 相關 SQL 的 join 條件或非 address 相關 update SQL 的 `PARTITION_DATE` 策略。
- **CON-003**: 不可修改不在需求範圍內的 schema、Pub/Sub 流程或 notebook 檔案。
- **GUD-001**: 所有變更完成後必須以既有 `tests/test_geocoding_batch_service.py`、`tests/test_google_maps_client_geocoding.py`、`tests/test_geocoding_models.py` 為基礎補足直接相關測試。
- **PAT-001**: global code 解析邏輯應集中在單一 helper 或單一 row-building 路徑中，避免在多處重複實作。

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: 完成程式邏輯調整，讓 request、response 解析與 GCS 儲存符合新版 Geocoding response 規則。

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-001|修改 `infrastructure/google_maps_client.py` 的 `GoogleMapsAPIClient.get_geocoding`：在 `params` dict 固定加入 `"fulfill_on_zero_results": "true"`；保留既有 `key`、`address`、`latlng`、timeout、retry 與 SSL verify 行為不變。|||
|TASK-002|修改 `application/geocoding_batch_process_service.py` 的 `GeocodingBatchProcessService._build_bq_row`：新增 deterministic global code 解析邏輯，先讀 `source_response.get("plus_code", {}).get("global_code")`，若空值再安全讀取 `source_response.get("results", [])[0].get("plus_code", {}).get("global_code")`。實作時不得假設 `results` 必定存在。|||
|TASK-003|修改 `application/geocoding_batch_process_service.py` 的 `GeocodingBatchProcessService._process_batch_records`：在成功驗證後，呼叫 `_build_bq_row(task_type, record, first_result, api_response)` 或等價簽章，使 row builder 同時可存取 `results[0]` 與 root-level response；不可改變現有 success/error/skipped 計數邏輯。|||
|TASK-004|修改 `application/geocoding_batch_process_service.py` 的 `GeocodingBatchProcessService._upload_success_rows_to_gcs` 與其呼叫資料：確認 `gcs_rows[].payload` 保存完整 `api_response`，且 `json.dumps(row.get("payload", {}), ensure_ascii=False)` 不做欄位裁切。若現況已保存完整 response，任務內容改為補充單元測試驗證此契約。|||
|TASK-005|檢查並必要時微調 `application/geocoding_batch_process_service.py` 的 `GeocodingBatchProcessService._call_geocoding_api`：contract coordinates 路徑僅以 `lat.strip()`、`lng.strip()` 組裝 `"{lat},{lng}"`，不得引入任何 `round`、`format`、`float(...):.4f` 或其他精度縮減。|||

### Implementation Phase 2

- **GOAL-002**: 完成 SQL 調整，使 address query/update 與 coordinate query 符合新的資料篩選與寫入規則。

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-006|修改 `sql/geocoding_query_contract_coordinates.sql`：在 `latest_hes_application` CTE 的 `FROM RAW_HES_DATASET.APPLICATION` 後新增 `WHERE status = "ACTIVE"`；保留現有 `QUALIFY ROW_NUMBER()` 結構。|||
|TASK-007|修改 `sql/geocoding_query_contract_coordinates.sql`：將 `latest_vmb_apply_info` CTE 內的 `ROUND(SAFE_CAST(longitude AS FLOAT64), 4)` 與 `ROUND(SAFE_CAST(latitude AS FLOAT64), 4)` 改為 `SAFE_CAST(longitude AS FLOAT64)`、`SAFE_CAST(latitude AS FLOAT64)`，其他 dedup/filter 條件不變。|||
|TASK-008|修改 `sql/geocoding_query_contact_address.sql`：在 `latest_hes_customer` CTE 補選 `current_application_id` 欄位，並將主查詢 `JOIN latest_hes_customer AS cust` 改為同時包含 `appl.customer_id = cust.id` 與 `appl.id = cust.current_application_id`。|||
|TASK-009|修改 `sql/geocoding_query_residence_address.sql`：在 `latest_hes_customer` CTE 補選 `current_application_id` 欄位，並將主查詢 `JOIN latest_hes_customer AS cust` 改為同時包含 `appl.customer_id = cust.id` 與 `appl.id = cust.current_application_id`。|||
|TASK-010|修改 `sql/geocoding_update_contact_address.sql`：在 `latest_hes_customer` CTE 補選 `current_application_id` 欄位，將 `JOIN latest_hes_customer AS cust` 改為雙條件 join，並將最終 `SELECT` 第一欄 `DATE_ADD(appl.partition_date, INTERVAL 1 DAY)` 改為 `CURRENT_DATE()`。|||
|TASK-011|修改 `sql/geocoding_update_residence_address.sql`：在 `latest_hes_customer` CTE 補選 `current_application_id` 欄位，將 `JOIN latest_hes_customer AS cust` 改為雙條件 join，並將最終 `SELECT` 第一欄改為 `CURRENT_DATE()`。|||
|TASK-012|修改 `sql/geocoding_update_contract_coordinates.sql`：使用 SQL block comment 或逐行 `--` 註解方式停用整份檔案，保留原內容可讀性；不可刪除檔案、不可只註解標頭。|||

### Implementation Phase 3

- **GOAL-003**: 更新文件與測試，確保新行為有明確規格與自動驗證覆蓋。

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-013|修改 `docs/SASD_GoogleMaps_Geocoding.md` 的「2.4 下行/回應 API 規格」與「2.5 下行/回應 API 範例」：將範例替換為新版 root-level `plus_code` + `results[]` 結構，欄位表需區分 root-level `plus_code.global_code` 與 result-level `plus_code.global_code` fallback。|||
|TASK-014|修改 `docs/SASD_GoogleMaps_Geocoding.md` 的「3.4 儲存下行 (BigQuery)」與附錄相關敘述：將 `RESPONSE_GLOBAL_CODE` 說明改成「優先取 root-level `plus_code.global_code`，無值時取 `results[0].plus_code.global_code`」，並檢查其餘描述是否仍假設 response 只有單筆 root object。|||
|TASK-015|更新 `tests/test_google_maps_client_geocoding.py`：新增或修改測試以驗證 `GoogleMapsAPIClient.get_geocoding` 送出的 `params` 含 `fulfill_on_zero_results=true`，且不影響 `address`/`latlng` 既有參數。|||
|TASK-016|更新 `tests/test_geocoding_batch_service.py`：新增或修改測試覆蓋 `RESPONSE_GLOBAL_CODE` root-level 優先、fallback 至 `results[0].plus_code.global_code`、`results=[]` 時不拋例外，以及 GCS 上傳 payload 保留 root-level `plus_code`/`status`。|||
|TASK-017|更新與 SQL 對應的測試檔案，優先檢查 `tests/test_geocoding_batch_service.py`、`tests/test_geocoding_edge_case.py` 是否有 SQL 內容斷言；若無現成測試，新增最小測試以驗證 address query/update 使用新 join 條件、coordinate query 不再 `ROUND(..., 4)`，以及 `status = "ACTIVE"` 存在於 `sql/geocoding_query_contract_coordinates.sql`。|||
|TASK-018|執行與本次變更直接相關的測試命令，至少涵蓋 `tests/test_google_maps_client_geocoding.py`、`tests/test_geocoding_batch_service.py`、`tests/test_geocoding_models.py`；若有 SQL 檔案內容測試亦一併執行，確認無回歸。|||

### Implementation Phase 4

- **GOAL-004**: 實作 ALT-001，將 Geocoding response 解析收斂到 Pydantic 模型層，並與既有批次流程對接。

|Task|Description|Completed|Date|
|---|---|---|---|
|TASK-019|修改 `models/geocoding_models.py`：新增 root-level `plus_code` 欄位模型（例如 `GeocodingRootPlusCode`）與對應欄位，保留既有 `results[0]` 結構驗證，確保新舊欄位可同時解析。|||
|TASK-020|修改 `models/geocoding_models.py`：新增統一輸出 helper（例如 `extract_global_code_with_fallback(parsed_response)`），邏輯固定為 root-level `plus_code.global_code` 優先，缺值時 fallback 到 `results[0].plus_code.global_code`。|||
|TASK-021|修改 `application/geocoding_batch_process_service.py`：在 `_build_bq_row` 內改用 `models/geocoding_models.py` 的 helper 取 `RESPONSE_GLOBAL_CODE`，移除 service 層重複的手動 dict 解析。|||
|TASK-022|更新 `tests/test_geocoding_models.py` 與 `tests/test_geocoding_batch_service.py`：新增 ALT-001 專用測試案例，涵蓋 root-level only、result-level only、雙方皆有值（必取 root-level）與雙方皆缺值（回傳 `None`）。|||

## 3. Alternatives

- **ALT-001**: 在 `models/geocoding_models.py` 內新增 root-level `plus_code` Pydantic schema 並全面重構 response mapping。狀態：已納入本計畫 `Implementation Phase 4` 執行。
- **ALT-002**: 建立新的 SQL 模板產生器統一 address/coordinate query。未採用原因：超出本次需求，且會擴大變更範圍。
- **ALT-003**: 刪除 `sql/geocoding_update_contract_coordinates.sql` 或從程式碼中移除其引用。未採用原因：需求明確要求整份 SQL 以註解方式停用並保留檔案。
- **ALT-004**: 將 `PARTITION_DATE` 改為在 Python 端統一填值。未採用原因：需求限定調整 address update SQL，且現有寫入路徑已由 SQL 決定該欄位。

## 4. Dependencies

- **DEP-001**: `application/geocoding_batch_process_service.py` 依賴 `services.google_maps_api_service.GoogleMapsAPIService.get_geocoding_result` 回傳完整 root-level response。
- **DEP-002**: `infrastructure/google_maps_client.py` 依賴 `modules.config.config.google_maps_geocoding_base_url`、`google_maps_timeout`、`google_maps_max_retries` 與 Secret Manager API key，不需新增設定鍵。
- **DEP-003**: `sql/geocoding_query_contact_address.sql`、`sql/geocoding_query_residence_address.sql`、`sql/geocoding_query_contract_coordinates.sql` 依賴 `RAW_HES_DATASET.APPLICATION`、`RAW_HES_DATASET.CUSTOMER`、`RAW_VMB_DATASET.APPLY_INFO` 現有欄位，包含 `current_application_id` 與 `status`。
- **DEP-004**: `tests/` 既有測試基礎使用 `unittest.mock` 與 monkeypatch/stub cloud clients；新測試應沿用相同模式，不新增測試框架。
- **DEP-005**: `docs/SASD_GoogleMaps_Geocoding.md` 與 `sql/` 檔案必須保持規格與實作同步，避免文件再次落後於實際 response 結構。

## 5. Files

- **FILE-001**: `infrastructure/google_maps_client.py` - 調整 `GoogleMapsAPIClient.get_geocoding` request params。
- **FILE-002**: `application/geocoding_batch_process_service.py` - 調整 global code 解析、GCS payload 契約與 contract latlng 精度保留。
- **FILE-003**: `sql/geocoding_query_contract_coordinates.sql` - 移除四位小數處理並新增 `status = "ACTIVE"`。
- **FILE-004**: `sql/geocoding_query_contact_address.sql` - address query join 條件改為雙條件。
- **FILE-005**: `sql/geocoding_query_residence_address.sql` - address query join 條件改為雙條件。
- **FILE-006**: `sql/geocoding_update_contact_address.sql` - address update join 條件與 `CURRENT_DATE()`。
- **FILE-007**: `sql/geocoding_update_residence_address.sql` - address update join 條件與 `CURRENT_DATE()`。
- **FILE-008**: `sql/geocoding_update_contract_coordinates.sql` - 整份註解停用。
- **FILE-009**: `docs/SASD_GoogleMaps_Geocoding.md` - 更新 response 範例、欄位說明與 `RESPONSE_GLOBAL_CODE` 規格描述。
- **FILE-010**: `tests/test_google_maps_client_geocoding.py` - 驗證 request params 新增 `fulfill_on_zero_results=true`。
- **FILE-011**: `tests/test_geocoding_batch_service.py` - 驗證 root-level global code 優先、fallback 與完整 GCS payload。
- **FILE-012**: `tests/test_geocoding_models.py` - 視需要確認 `results` 為空時 validation/fallback 行為不產生未處理錯誤。
- **FILE-013**: `models/geocoding_models.py` - ALT-001 的 root-level plus_code schema 與 global code fallback helper。

## 6. Testing

- **TEST-001**: `tests/test_google_maps_client_geocoding.py` 驗證 `GoogleMapsAPIClient.get_geocoding(address=...)` 與 `get_geocoding(latlng=...)` 都帶有 `fulfill_on_zero_results=true`。
- **TEST-002**: `tests/test_geocoding_batch_service.py` 驗證 `_build_bq_row` 或等價流程在 root-level `plus_code.global_code` 存在時，`RESPONSE_GLOBAL_CODE` 取 root-level 值。
- **TEST-003**: `tests/test_geocoding_batch_service.py` 驗證當 root-level `plus_code.global_code` 缺失時，`RESPONSE_GLOBAL_CODE` fallback 至 `results[0].plus_code.global_code`。
- **TEST-004**: `tests/test_geocoding_batch_service.py` 驗證當 `results` 為空且 root-level 無 `global_code` 時，不會因 fallback 存取而拋出 `IndexError` 或 `KeyError`。
- **TEST-005**: `tests/test_geocoding_batch_service.py` 驗證上傳至 GCS 的 payload 包含 root-level `status` 與 root-level `plus_code`，而非僅 `results[0]`。
- **TEST-006**: SQL 內容測試或檔案斷言驗證 `sql/geocoding_query_contract_coordinates.sql` 不含 `ROUND(`，且包含 `status = "ACTIVE"`。
- **TEST-007**: SQL 內容測試或檔案斷言驗證 `sql/geocoding_query_contact_address.sql` 與 `sql/geocoding_query_residence_address.sql` 包含 `appl.id = cust.current_application_id`。
- **TEST-008**: SQL 內容測試或檔案斷言驗證 `sql/geocoding_update_contact_address.sql` 與 `sql/geocoding_update_residence_address.sql` 使用 `CURRENT_DATE()` 作為 `PARTITION_DATE`。
- **TEST-009**: SQL 內容測試或檔案斷言驗證 `sql/geocoding_update_contract_coordinates.sql` 全檔已註解停用。
- **TEST-010**: `tests/test_geocoding_models.py` 驗證 ALT-001 模型在 root-level only/result-level only/雙值同時存在/雙值缺失情境下，global code 輸出符合優先序規則。
- **TEST-011**: `tests/test_geocoding_batch_service.py` 驗證 `_build_bq_row` 已透過模型 helper 取得 `RESPONSE_GLOBAL_CODE`，避免 service 層自建 fallback 分支。

## 7. Risks & Assumptions

- **RISK-001**: 若 `RAW_HES_DATASET.CUSTOMER` 不存在 `current_application_id` 欄位，address query/update SQL 將失敗；執行前需以現有 schema 或 BQ 文件確認欄位存在。
- **RISK-002**: 若部分測試直接斷言舊版 `DATE_ADD(appl.partition_date, INTERVAL 1 DAY)` 或 `ROUND(..., 4)` 字串，修改 SQL 後需同步更新斷言。
- **RISK-003**: `sql/geocoding_update_contract_coordinates.sql` 被整份註解後，若執行流程仍無條件呼叫該檔案，BigQuery query 行為可能變成 no-op；需確認現行流程允許 update SQL 無實際執行內容。
- **ASSUMPTION-001**: `application/geocoding_batch_process_service.py` 現有 `gcs_rows.append({"payload": api_response})` 已代表完整 response；需求 4 主要是保證此契約不被 row builder 裁切。
- **ASSUMPTION-002**: `RESPONSE_ADDRESS`、`RESPONSE_PLACE_TYPES` 等 BigQuery 欄位仍維持從 `results[0]` 取得，只有 `RESPONSE_GLOBAL_CODE` 需要 root-level 優先。
- **ASSUMPTION-003**: 本次不需要修改 notebook `geocoding連線測試.ipynb`，因使用者要求的是正式程式與文件調整的 implementation plan。

## 8. Related Specifications / Further Reading

[docs/SASD_GoogleMaps_Geocoding.md](../docs/SASD_GoogleMaps_Geocoding.md)
[application/geocoding_batch_process_service.py](../application/geocoding_batch_process_service.py)
[infrastructure/google_maps_client.py](../infrastructure/google_maps_client.py)
[sql/geocoding_query_contract_coordinates.sql](../sql/geocoding_query_contract_coordinates.sql)
[sql/geocoding_update_contact_address.sql](../sql/geocoding_update_contact_address.sql)
