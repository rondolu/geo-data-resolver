---
goal: Geocoding Pipeline Integration Plan for geo-data-resolver
version: 1.0
date_created: 2026-04-01
last_updated: 2026-04-01
owner: Data Engineering
status: Planned
tags: [feature, geocoding, pubsub, batch, architecture]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

本計畫定義在 `geo-data-resolver` 以最小改動原則整合 Geocoding 三階段批次流程，並與既有 `place_aggregate` 鏈式 Pub/Sub、daily recall、api_log/flow_log、cloud logging 行為對齊；最終於第三階段完成後才呼叫 anonymization。

## 1. Requirements & Constraints

- **REQ-001**: `place_aggregate` 最後步驟改為發布訊息到 `geo-data-resolver` topic，且 attributes 必含 `category=geocoding`。
- **REQ-002**: 新增 HTTP router `POST /geocoding` 供 subscription 呼叫，成功時回傳 HTTP 204。
- **REQ-003**: Geocoding 任務必須依序執行三階段：`contact_address`、`residence_address`、`contract_coordinates`。
- **REQ-004**: 每一階段先執行附錄四/五/六對應的 INSERT SQL，再執行附錄一/二/三對應的 SELECT 發查清單與逐筆 API 呼叫。
- **REQ-005**: 每階段僅支援 daily recall；不實作 range recall。
- **REQ-006**: 當 `is_last_batch=True` 且該階段批次完成時，發布下一階段 Pub/Sub 訊息。
- **REQ-007**: 第三階段完成後發布 anonymization topic，`file_list=["RAW_EDEP_DATASET.GEOCODING"]`。
- **REQ-008**: Geocoding API 回應必須經過 Pydantic 驗證，至少符合 SASD 附錄七規則。
- **REQ-009**: Geocoding API key 與既有 Area Insights 共用同一 Secret Manager 金鑰。
- **REQ-010**: `REQUEST_DENIED` 需立即終止流程並 raise error，且寫入 cloud logging。
- **REQ-011**: `UNKNOWN_ERROR` 固定間隔 30 秒重試，最多 3 次；重試次數解讀需對齊既有 retry 計數慣例；失敗後終止並 raise error。
- **REQ-012**: 僅成功回應資料可寫入 GCS；附錄四/五/六 INSERT SQL 不得觸發 GCS 寫入。
- **REQ-013**: BigQuery 欄位使用 `RESPONSE_ADDRESS`（已修正）。
- **REQ-014**: SQL 檔案中的 dataset/table 名稱維持寫死，不進行參數注入。
- **SEC-001**: 禁止在程式碼硬編碼 API key；必須透過既有 Secret Manager 讀取流程。
- **OPS-001**: api_log / flow_log 與 cloud logging 時機需與既有 `place_aggregate` 對齊。
- **CON-001**: 採用最小改動原則，不可破壞既有 `/` 與 `/get_data_range` 行為。
- **CON-002**: 優先重用既有 `Configuration` property；僅新增必要 property。
- **PAT-001**: 延用既有 `BatchProcessService` + `DataflowService` + `PubSubService` 編排模式。
- **PAT-002**: 錯誤處理沿用既有例外型別與 logging 寫法（`_logger.log_text` + raised exception）。

## 2. Implementation Steps

### Implementation Phase 1

- **GOAL-001**: 建立 Geocoding 流程骨架與路由入口，確保 Pub/Sub 可導流並可判斷階段。

| Task | Description | Completed | Date |
| -------- | --------------------- | --------- | ---------- |
| TASK-001 | 在 `blueprints/geo_routes.py` 新增 `POST /geocoding` 路由，重用既有 `is_pubsub_request`、例外處理與成功時 `return "", 204` 行為。 |  |  |
| TASK-002 | 在 `services/` 新增 Geocoding orchestration service（建議 `services/geocoding_flow_service.py`），實作 `handle_geocoding_request`、`process_stage`、`process_recall_batch`，訊息欄位固定支援 `message_type=daily_recall` 與 `task_type`。 |  |  |
| TASK-003 | 在 `utils/pubsub_services.py` 新增 Geocoding 專用發布方法：`publish_geocoding_stage_start(task_type, batch_number=1)`、`publish_geocoding_daily_recall(task_type, current_batch)`，attributes 必含 `category=geocoding`。 |  |  |
| TASK-004 | 在 `application/batch_process_service.py` 修改 place_aggregate 最後步驟：以 `_publish_geocoding_notification()` 取代原本直接 anonymization 呼叫，發布 `task_type=contact_address`。 |  |  |
| TASK-005 | 在 `services/dataflow_service.py` 與現有流程保留相容，不改動 `/`、`/get_data_range` 既有 API 協定；必要時僅加入非侵入式呼叫點。 |  |  |
| TASK-006 | 完成契約驗證：針對 Pub/Sub payload 格式補上必填欄位檢核（`task_type`, `batch_number`）與錯誤回應 400。 |  |  |

### Implementation Phase 2

- **GOAL-002**: 實作 Geocoding API、Pydantic 驗證、三階段 SQL 與資料寫入邏輯。

| Task | Description | Completed | Date |
| -------- | --------------------- | --------- | ---------- |
| TASK-007 | 在 `models/` 新增 Geocoding Pydantic 模型（建議 `models/geocoding_models.py`），最小包含 `status`、`results[0].formatted_address`、`geometry.location.lat/lng`、`address_components` 驗證器。 |  |  |
| TASK-008 | 在 `infrastructure/google_maps_client.py` 新增 Geocoding API client method（建議 `get_geocoding(address=None, latlng=None)`）；重用現有 session、timeout、retry 計數慣例。 |  |  |
| TASK-009 | 在 `services/google_maps_api_service.py` 新增 Geocoding service method（建議 `get_geocoding_result(...)`），封裝 REQUEST_DENIED/UNKNOWN_ERROR 特例：`REQUEST_DENIED` 立即 raise；`UNKNOWN_ERROR` 固定 30 秒重試最多 3 次（計數對齊既有）。 |  |  |
| TASK-010 | 在 `application/` 新增 Geocoding batch service（建議 `application/geocoding_batch_process_service.py`），重用 `BatchContext` 與批次函式模式，實作每階段「INSERT SQL -> SELECT SQL -> 逐筆 API -> 批次寫 GCS/BQ」。 |  |  |
| TASK-011 | 新增 SQL 檔案到 `sql/`：`geocoding_query_contact_address.sql`、`geocoding_query_residence_address.sql`、`geocoding_query_contract_coordinates.sql`、`geocoding_update_contact_address.sql`、`geocoding_update_residence_address.sql`、`geocoding_update_contract_coordinates.sql`；dataset/table 名稱寫死。 |  |  |
| TASK-012 | 在 `application/bigquery_service.py` 擴充 GEOCODING 表寫入方法（建議 `insert_geocoding_rows`），欄位採 `RESPONSE_ADDRESS`。 |  |  |
| TASK-013 | 在 `utils/gcs_services.py` 重用 `upload_rows_as_json`，於 Geocoding pipeline 端控制僅成功回應寫入，並使用路徑前綴 `GOOGLEMAPS/GEOCODING`。 |  |  |
| TASK-014 | 在 Geocoding pipeline 中加入 `extract_address_component` 公用函式（可置於 `utils/data_processor.py` 或新檔）以提取國家/城市/行政區/路名。 |  |  |

### Implementation Phase 3

- **GOAL-003**: 完成階段切換、最終 anonymization 發布、logging 對齊與可驗證測試。

| Task | Description | Completed | Date |
| -------- | --------------------- | --------- | ---------- |
| TASK-015 | 在 Geocoding orchestrator 實作階段狀態機：`contact_address -> residence_address -> contract_coordinates`，僅在 `is_last_batch=True` 且該階段完成時切換。 |  |  |
| TASK-016 | 在第三階段完成點發布 anonymization 訊息（topic 使用 `config.anonymization_pubsub_topic`，payload `file_list=["RAW_EDEP_DATASET.GEOCODING"]`）。 |  |  |
| TASK-017 | 對齊 logging：在 Geocoding service/batch 中複製 place_aggregate 的 `api_log`、`flow_log`、關鍵 `_logger.log_text` 時機點。 |  |  |
| TASK-018 | 補齊 configuration：於 `config/config.yaml` 新增最小 Geocoding 設定（可共用則不新增）；於 `modules/config.py` 只補必要 property。 |  |  |
| TASK-019 | 新增/更新單元測試與整合測試（`tests/`）：路由 204、階段切換、REQUEST_DENIED 終止、UNKNOWN_ERROR 重試後終止、成功寫 GCS/BQ、第三階段後 anonymization。 |  |  |
| TASK-020 | 執行測試與靜態檢查，產出可驗證結果（所有新測試通過，既有主要流程測試未退化）。 |  |  |

## 3. Alternatives

- **ALT-001**: 以獨立 Cloud Run Job 實作 Geocoding 並由 Scheduler 直接觸發。未採用原因：違反「需由 place_aggregate 完成後鏈式觸發」需求。
- **ALT-002**: 以單一路由 `/` 接收 geocoding 任務，不新增 `/geocoding`。未採用原因：無法滿足 subscription filter 導流與明確責任分離。
- **ALT-003**: 將三階段資料以單一 SQL UNION 一次處理。未採用原因：不符合明確階段順序與 `is_last_batch` 切換規則。
- **ALT-004**: 對 SQL 使用動態 dataset/table 注入。未採用原因：需求明確指定 SQL 需寫死。

## 4. Dependencies

- **DEP-001**: `google-cloud-pubsub`（既有）供發布 stage start / recall / anonymization。
- **DEP-002**: `google-cloud-bigquery`（既有）供 INSERT/SELECT SQL 與結果寫入。
- **DEP-003**: `google-cloud-storage`（既有）供成功結果批次上傳 GCS。
- **DEP-004**: `pydantic`（若專案尚未使用需新增版本鎖定）供 Geocoding response 驗證。
- **DEP-005**: `requests`（既有）供 Geocoding HTTP GET 呼叫。

## 5. Files

- **FILE-001**: `blueprints/geo_routes.py` - 新增 `/geocoding` 路由與 Pub/Sub 回呼處理分派。
- **FILE-002**: `application/batch_process_service.py` - place_aggregate 結尾改發布 geocoding 啟動訊息。
- **FILE-003**: `utils/pubsub_services.py` - 新增 geocoding stage start / daily recall 發布方法。
- **FILE-004**: `services/google_maps_api_service.py` - 新增 Geocoding API 封裝與錯誤策略。
- **FILE-005**: `infrastructure/google_maps_client.py` - 新增 Geocoding API client method。
- **FILE-006**: `modules/config.py` - 補必要 Geocoding property（可共用則共用）。
- **FILE-007**: `config/config.yaml` - Geocoding 最小配置擴充。
- **FILE-008**: `application/bigquery_service.py` - GEOCODING rows 寫入方法。
- **FILE-009**: `utils/data_processor.py` - Geocoding row mapping / component extraction（若選擇重用此檔）。
- **FILE-010**: `models/geocoding_models.py` - Geocoding Pydantic models（新檔）。
- **FILE-011**: `application/geocoding_batch_process_service.py` - Geocoding 批次流程（新檔）。
- **FILE-012**: `services/geocoding_flow_service.py` - Geocoding 編排服務（新檔）。
- **FILE-013**: `sql/geocoding_query_contact_address.sql` - 附錄一 SQL。
- **FILE-014**: `sql/geocoding_query_residence_address.sql` - 附錄二 SQL。
- **FILE-015**: `sql/geocoding_query_contract_coordinates.sql` - 附錄三 SQL。
- **FILE-016**: `sql/geocoding_update_contact_address.sql` - 附錄四 SQL。
- **FILE-017**: `sql/geocoding_update_residence_address.sql` - 附錄五 SQL。
- **FILE-018**: `sql/geocoding_update_contract_coordinates.sql` - 附錄六 SQL。
- **FILE-019**: `tests/test_geocoding_route.py` - 路由與 Pub/Sub 訊息契約測試（新檔）。
- **FILE-020**: `tests/test_geocoding_flow.py` - 三階段與 recall 流程測試（新檔）。

## 6. Testing

- **TEST-001**: `/geocoding` 接收 `category=geocoding` Pub/Sub 訊息後成功回傳 204。
- **TEST-002**: `task_type=contact_address` 時必定先執行 `geocoding_update_contact_address.sql` 再執行 `geocoding_query_contact_address.sql`。
- **TEST-003**: 當 `is_last_batch=True` 且階段一完成，發布下一階段訊息 `task_type=residence_address`。
- **TEST-004**: 當 `is_last_batch=True` 且階段二完成，發布下一階段訊息 `task_type=contract_coordinates`。
- **TEST-005**: 當 `is_last_batch=True` 且階段三完成，發布 anonymization 訊息且 `file_list=["RAW_EDEP_DATASET.GEOCODING"]`。
- **TEST-006**: Geocoding response 驗證：缺少 `formatted_address`、`lat/lng`、`address_components` 時被拒絕寫入。
- **TEST-007**: `REQUEST_DENIED` 立即 raise error，且有 cloud logging 記錄。
- **TEST-008**: `UNKNOWN_ERROR` 依既有 retry 計數慣例執行 30 秒間隔重試至上限，仍失敗則 raise error。
- **TEST-009**: 成功回應才會寫入 GCS；INSERT SQL 執行結果不寫入 GCS。
- **TEST-010**: BQ 寫入欄位名稱驗證：使用 `RESPONSE_ADDRESS`。
- **TEST-011**: 回歸測試：`/` 與 `/get_data_range` 既有流程不退化。

## 7. Risks & Assumptions

- **RISK-001**: Geocoding API 回應結構可能因地區或結果型態差異造成欄位缺失，導致有效資料被過度過濾。
- **RISK-002**: `UNKNOWN_ERROR` 30 秒固定重試可能延長作業時間，對大型批次造成逾時風險。
- **RISK-003**: 若 Pub/Sub attributes 未正確帶入 `category=geocoding`，subscription 將無法導流到 `/geocoding`。
- **RISK-004**: 三階段狀態機若實作錯誤可能造成階段重入或跳階。
- **ASSUMPTION-001**: 既有 Secret Manager 金鑰可同時授權 Geocoding 與 Area Insights 呼叫。
- **ASSUMPTION-002**: Geocoding 需求僅 daily recall，不需對 `/get_data_range` 增加 geocoding range 模式。
- **ASSUMPTION-003**: 既有 logging 基礎設施（cloud logging、api_log、flow_log）可直接重用於 Geocoding 新流程。

## 8. Related Specifications / Further Reading

[SASD_GoogleMaps_Geocoding.md](../SASD_GoogleMaps_Geocoding.md)
[Google Maps Geocoding API 官方文件](https://developers.google.com/maps/documentation/geocoding/requests-geocoding?hl=zh-tw)
