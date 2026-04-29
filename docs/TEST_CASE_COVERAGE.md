# Test Coverage Guide

本文件為 `tests/` 資料夾的靜態快照，供管理者與稽核者確認自動化測試計畫的涵蓋完整性。  
Version: 2026-04-10 | Framework: pytest | Total cases: 35

---

## 概覽

| 測試檔案 | 測試層級 | 案例數 |
| --- | --- | --- |
| `test_geocoding_models.py` | 模型驗證 | 3 |
| `test_geocoding_route.py` | HTTP 路由層 | 2 |
| `test_geocoding_flow.py` | 流程狀態轉換 | 5 |
| `test_geocoding_batch_service.py` | 批次處理邏輯 | 10 |
| `test_google_maps_client_geocoding.py` | Google Maps Client | 2 |
| `test_geocoding_edge_case.py` | 邊界情境與韌性 (O/X) | 13 |
| **合計** | | **35** |

> **O 系列**：正向案例（正常路徑）｜**X 系列**：反向案例（錯誤路徑）

---

## 1. test_geocoding_models.py — 模型驗證

| 測試函式 | 說明 |
| --- | --- |
| `test_validate_geocoding_response_success` | 驗證完整 Geocoding 回應可通過檢核 |
| `test_validate_geocoding_response_missing_fields` | 驗證缺少必要欄位時 Geocoding 回應檢核會失敗 |
| `test_extract_address_component` | 驗證地址元件擷取可正確命中與回傳缺失類型 |

---

## 2. test_geocoding_route.py — HTTP 路由層

| 測試函式 | 說明 |
| --- | --- |
| `test_pubsub_success_returns_204` | 驗證 Pub/Sub 格式請求成功時回傳 HTTP 204 |
| `test_non_pubsub_returns_json` | 驗證一般 HTTP 請求會回傳 JSON 內容 |

---

## 3. test_geocoding_flow.py — 流程狀態轉換

| 測試函式 | 說明 |
| --- | --- |
| `test_completed_contact_stage_publishes_next_stage` | 驗證 `contact_address` 完成後會發布下一個 stage |
| `test_completed_final_stage_publishes_anonymization` | 驗證最終 stage 完成後會發布 anonymization 訊息 |
| `test_processing_contact_stage_publishes_daily_recall` | 驗證 `processing` 狀態下會發布 daily recall 訊息 |
| `test_request_denied_returns_geo_error` | 驗證 `REQUEST_DENIED` 會映射為 403 的 `geo_error` 回應 |
| `test_invalid_payload_returns_400` | 驗證缺少必要欄位的 payload 會回傳 400 |

---

## 4. test_geocoding_batch_service.py — 批次處理邏輯

| 測試函式 | 說明 |
| --- | --- |
| `test_first_batch_runs_update_sql` | 驗證第一個批次會先執行更新 SQL 再進行處理 |
| `test_non_first_batch_runs_update_sql` | 驗證非第一個批次同樣會先執行更新 SQL 再進行處理 |
| `test_unknown_error_raises_in_batch_records` | 驗證批次記錄遇到 `UNKNOWN_ERROR` 時會拋出例外 |
| `test_request_denied_raises_in_first_record` | 驗證批次記錄遇到 `REQUEST_DENIED` 時會拋出例外 |
| `test_non_fatal_error_continues_to_next_record` | 驗證非致命錯誤發生後會繼續處理下一筆記錄 |
| `test_zero_results_skips_without_raising` | 驗證 `ZERO_RESULTS` 回應會被略過而不拋出例外 |
| `test_call_geocoding_api_raises_for_empty_address` | 驗證空白的 `request_address` 欄位會拋出 `ValueError` |
| `test_call_geocoding_api_raises_for_missing_contract_coordinates` | 驗證缺少座標資訊的合約座標任務會拋出 `ValueError` |
| `test_call_geocoding_api_invalid_coordinates_bubble_up_api_error` | 驗證無效座標 payload 會將 API 錯誤往上傳遞 |
| `test_call_geocoding_api_very_long_address_bubble_up_api_error` | 驗證超長地址 payload 會將 API 錯誤往上傳遞 |

---

## 5. test_google_maps_client_geocoding.py — Google Maps Client

| 測試函式 | 說明 |
| --- | --- |
| `test_unknown_error_retries_and_raises` | 驗證 `UNKNOWN_ERROR` 會重試至上限後拋出錯誤 |
| `test_request_denied_raises_immediately` | 驗證 `REQUEST_DENIED` 發生時不重試並立即拋錯 |

---

## 6. test_geocoding_edge_case.py — 邊界情境與韌性

### O 系列：正向案例（正常路徑）

| 測試函式 | 說明 |
| --- | --- |
| `test_o1_access_gcp_resources` | 驗證核心服務可正常初始化並可存取 GCP 相關資源 |
| `test_o2_normal_request_under_rate_limit` | 驗證符合速率限制時可成功取得 Geocoding 回應 |
| `test_o3_response_pass_pydantic` | 驗證完整回應可通過 Pydantic 檢核 |
| `test_o4_write_to_gcs_and_bq` | 驗證成功查詢資料會寫入 GCS 與 BigQuery |
| `test_o5_pubsub_recall_success` | 驗證非最後批次時會成功觸發 recall callback |
| `test_o6_pubsub_filter_and_correct_task_sql` | 驗證 Pub/Sub category 與 `task_type` 路由邏輯正確 |
| `test_o7_publish_anonymization_at_end` | 驗證最後階段完成後會發布 anonymization 訊息 |
| `test_o8_each_request_writes_api_log` | 驗證每次 Geocoding 呼叫都會寫入 api_log |

### X 系列：反向案例（錯誤路徑）

| 測試函式 | 說明 |
| --- | --- |
| `test_x1_error_does_not_crash_pipeline` | 驗證單筆非致命錯誤不會中斷整體管線 |
| `test_x2_request_error_caught` | 驗證請求層 API 錯誤可被接住並累計錯誤數 |
| `test_x3_retry_policy_executes` | 驗證暫時性失敗時會觸發重試並可恢復成功 |
| `test_x4_failed_request_written_to_flow_log` | 驗證無效任務輸入造成失敗時會寫入 flow_log |
| `test_x5_no_recall_on_last_batch_to_avoid_loop` | 驗證最後批次不會觸發 recall 以避免無限迴圈 |

---

## 附註

- 所有測試使用 `unittest.mock` 進行 GCP 相依性隔離（`BigQueryService`、`GCSService`、`SecretManagerService`）
- 此文件為靜態快照，新增或刪除測試案例時需手動同步更新
