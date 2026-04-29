# Geocoding 流程日誌盤點

本文件詳細記錄 Geocoding 三階段批次流程中所有的 flow_log 與 Cloud Logging 寫入點。

---

## 1. Flow Log 寫入盤點

### 1.1 透過 `@Logging.logtobq` 裝飾器自動寫入

此裝飾器會自動在方法成功或失敗時寫入 flow_log 到 BigQuery，並在特定條件下寫入 Cloud Logging。

| task_code | 位置 | 函式 | 觸發時機 |
|-----------|------|------|--------|
| `003` | [blueprints/geo_routes.py](blueprints/geo_routes.py#L115) | `geocoding_entry()` | POST `/geocoding` 路由被呼叫時 |
| `31` | [application/geocoding_batch_process_service.py](application/geocoding_batch_process_service.py#L65) | `process_stage()` | 每次呼叫單一階段批次時 |
| `32` | [application/geocoding_batch_process_service.py](application/geocoding_batch_process_service.py#L96) | `_execute_update_sql()` | 每個 batch 執行 INSERT SQL 時 |
| `33` | [application/geocoding_batch_process_service.py](application/geocoding_batch_process_service.py#L112) | `_process_single_batch()` | 每批次結果彙整時 |
| `34` | [application/geocoding_batch_process_service.py](application/geocoding_batch_process_service.py#L141) | `_process_batch_records()` | 逐筆 API 呼叫與寫入時 |

### 1.2 直接呼叫 `log.flowlog()`

| 位置 | 觸發條件 | task_code | severity | 內容 |
|------|---------|-----------|----------|------|
| [services/geocoding_flow_service.py](services/geocoding_flow_service.py#L113) | 第三階段（`contract_coordinates`）完成且 anonymization 發布後 | `01` | Notice | `"All job completed"` |

---

## 2. Cloud Logging 寫入盤點

### 2.1 一定會寫 Cloud Logging 的點

以下呼叫直接使用 `_logger.log_text()` 或 `_logger.log_struct()`，會立即寫入 Cloud Logging：

| 位置 | 函式 | severity | 觸發條件 | 描述 |
|------|------|----------|--------|------|
| [services/geocoding_flow_service.py](services/geocoding_flow_service.py#L50) | `handle_geocoding_request()` | Error | 未預期例外 | 路由層捕獲異常 |
| [services/geocoding_flow_service.py](services/geocoding_flow_service.py#L94) | `_publish_next_action()` | Notice | 階段切換成功 | 轉移到下一階段（contact→residence→contract） |
| [services/geocoding_flow_service.py](services/geocoding_flow_service.py#L106) | `_publish_next_action()` | Notice | 第三階段完成 | 發布 anonymization 訊息 |
| [application/geocoding_batch_process_service.py](application/geocoding_batch_process_service.py#L101) | `_execute_update_sql()` | Info | 更新 SQL 執行成功 | 記錄執行的 SQL 檔案名 |
| [application/geocoding_batch_process_service.py](application/geocoding_batch_process_service.py#L109) | `_load_query_data()` | Error | 查詢 SQL 失敗 | 記錄查詢失敗原因 |
| [application/geocoding_batch_process_service.py](application/geocoding_batch_process_service.py#L179) | `_process_batch_records()` | Error | REQUEST_DENIED 或 UNKNOWN_ERROR | 致命 API 錯誤，導致流程終止 |
| [application/geocoding_batch_process_service.py](application/geocoding_batch_process_service.py#L183) | `_process_batch_records()` | Warning | 非致命 API 錯誤 | 單筆記錄略過，流程繼續 |
| [application/geocoding_batch_process_service.py](application/geocoding_batch_process_service.py#L187) | `_process_batch_records()` | Warning | 未知錯誤 | 單筆記錄處理異常 |
| [application/geocoding_batch_process_service.py](application/geocoding_batch_process_service.py#L279) | `_insert_rows_to_bq()` | Error | BigQuery 寫入失敗 | 成功資料未能存入 BQ |
| [services/google_maps_api_service.py](services/google_maps_api_service.py#L258) | `get_geocoding_result()` | Error | Geocoding API 例外 | 記錄 API 呼叫失敗 |
| [blueprints/geo_routes.py](blueprints/geo_routes.py#L140) | `geocoding_entry()` | Error | 未處理的例外 | 路由層捕獲異常 |

### 2.2 條件式寫 Cloud Logging 的點

以下作機制會根據結果狀態決定是否寫入 Cloud Logging：

#### 2.2.1 裝飾器 `@Logging.logtobq` 的條件規則

**Cloud Logging 寫入條件**（控制在 [utils/infra_logging.py](utils/infra_logging.py#L228-L245)）：

- **失敗時**：若 HTTP status_code >= 400 或拋出例外，severity 為 `Error`，**一定寫入** structured Cloud Logging
- **成功時**：status_code 為 2xx，severity 為 `Info`，**不寫入** structured Cloud Logging
- **特殊 prefix**：若回傳值以 `"DEBUG:"` 開頭，severity 為 `Debug`，**不寫入**；若以 `"NOTICE:"` 開頭，severity 為 `Notice`，**會寫入**

**Geocoding 流程中的 5 個裝飾器**：

| task_code | 函式 | 正常情況 | 異常情況 |
|-----------|------|--------|--------|
| `003` | `geocoding_entry()` | 回 200 (Info，不寫) | 回 >=400 或例外 (Error，寫) |
| `31` | `process_stage()` | Success (Info，不寫) | Exception (Error，寫) |
| `32` | `_execute_update_sql()` | 成功 (Info，不寫) | Exception (Error，寫) |
| `33` | `_process_single_batch()` | 成功 (Info，不寫) | Exception (Error，寫) |
| `34` | `_process_batch_records()` | 成功 (Info，不寫) | Exception (Error，寫) |

#### 2.2.2 `apilog()` 方法的 Cloud Logging 規則

**Cloud Logging 寫入條件**（控制在 [utils/infra_logging.py](utils/infra_logging.py#L189)）：

- 若 `status_code` 以 `'4'` 或 `'5'` 開頭（4xx 或 5xx），severity 為 `ERROR`，**寫入** structured Cloud Logging
- 否則 severity 為 `Info`，**不寫入**

**Geocoding 中呼叫 apilog 的點**：

| 位置 | 函式 | 時機 | Cloud Logging 寫入條件 |
|------|------|------|--------|
| [services/google_maps_api_service.py](services/google_maps_api_service.py#L223) | `get_geocoding_result()` | API 成功 | status_code="200"，不寫 |
| [services/google_maps_api_service.py](services/google_maps_api_service.py#L244) | `get_geocoding_result()` | API 失敗 | 拋例外前，status_code 可能 >=400，寫入 |

#### 2.2.3 `flowlog()` 方法的 Cloud Logging 規則

**Cloud Logging 寫入條件**（控制在 [utils/infra_logging.py](utils/infra_logging.py#L139-L149)）：

- 若 `severity` 非 `"Info"` 或 `"INFO"`，**寫入** structured Cloud Logging
- 若 `severity` 為 `"Info"`，**不寫入**

**Geocoding 中直接呼叫 flowlog 的點**：

| 位置 | severity | Cloud Logging 寫入 |
|------|----------|----------------|
| [services/geocoding_flow_service.py](services/geocoding_flow_service.py#L113) | Notice | 是（Notice != Info） |

---

## 3. 流程全景摘要

### 3.1 Geocoding 完整流程的日誌記錄點

```
POST /geocoding 
  ↓ @Logging.logtobq(task_code="003")  [flowlog + 條件 Cloud Logging]
  ↓
GeocodingFlowService.handle_geocoding_request()
  ├─ _logger.log_text(..., severity="Error")  [Cloud Logging]  [例外時]
  ├─ process_stage()
  │  ├─ @Logging.logtobq(task_code="31")  [flowlog + 條件 Cloud Logging]
  │  ├─ _execute_update_sql()  (每個 batch 都執行)
  │  │  ├─ @Logging.logtobq(task_code="32")  [flowlog + 條件 Cloud Logging]
  │  │  └─ _logger.log_text(..., severity="Info")  [Cloud Logging]
  │  ├─ _load_query_data()
  │  │  └─ _logger.log_text(..., severity="Error")  [Cloud Logging]  [失敗時]
  │  ├─ _process_single_batch()
  │  │  ├─ @Logging.logtobq(task_code="33")  [flowlog + 條件 Cloud Logging]
  │  │  └─ _process_batch_records()
  │  │     ├─ @Logging.logtobq(task_code="34")  [flowlog + 條件 Cloud Logging]
  │  │     ├─ get_geocoding_result()
  │  │     │  ├─ log.apilog(...)  [BQ + 條件 Cloud Logging]
  │  │     │  └─ _logger.log_text(..., severity="Error")  [Cloud Logging]  [失敗時]
  │  │     ├─ _logger.log_text(..., severity="Error/Warning")  [Cloud Logging]  [各類錯誤]
  │  │     ├─ _upload_success_rows_to_gcs()
  │  │     └─ _insert_rows_to_bq()
  │  │        └─ _logger.log_text(..., severity="Error")  [Cloud Logging]  [失敗時]
  │  └─ callback_handler()  -> publish_geocoding_daily_recall()
  │
  ├─ _publish_next_action()
  │  ├─ _logger.log_text(..., severity="Notice")  [Cloud Logging]  [階段切換]
  │  └─ flowlog(..., severity="Notice")  [Cloud Logging]  [最終完成]
  │
  └─ return 204 (Pub/Sub) or 200/4xx (HTTP)
```

### 3.2 日誌分層總結

| 日誌類型 | 寫入位置 | 觸發條件 | Cloud Logging 寫入頻率 |
|---------|--------|--------|------------------|
| **flow_log** | BigQuery FLOW_LOG | 5×裝飾器 + 1×直接呼叫 | 失敗或特定 severity 時 |
| **api_log** | BigQuery API_LOG | get_geocoding_result() 成功/失敗 | 4xx/5xx 時 |
| **text_log** | Cloud Logging 即時 | _logger.log_text() 直接呼叫 | 立即寫入 |
| **struct_log** | Cloud Logging 結構化 | flowlog/apilog 條件觸發 | 依 severity/status_code |

---

## 4. 設定與表寫入詳情

### 4.1 BigQuery 表設定

```yaml
flow_log_dataset: "LOG_DATASET"
flow_log_table: "FLOW_LOG"
api_log_dataset: "API_DATASET"
api_log_table: "API_LOG"
geocoding_table: "GEOCODING"
```

### 4.2 Flow Log Row 結構

```json
{
  "FLOW_ID": "{flow_name}_{log_uuid}",
  "DATETIME": "YYYY-MM-DD HH:MM:SS",
  "FLOW_NAME": "geocoding_batch_process_service",
  "TASK_CODE": "E06{task_code}",
  "TASK_NAME": "process_stage",
  "STATUS": "Success|Error",
  "MESSAGE": "{描述}",
  "SEVERITY": "Info|Debug|Error|Notice"
}
```

### 4.3 API Log Row 結構

```json
{
  "UUID_Request": "{log_uuid}",
  "API_Type": "geo-data-resolver-api",
  "API_Name": "geocoding-api",
  "Start_Time": "2026-04-08T12:00:00",
  "End_Time": "2026-04-08T12:00:05",
  "Status_Code": "200|4xx|5xx",
  "Status_Detail": "Success - Geocoding status: {status}",
  "Retry": {retry_count}
}
```

---

## 5. 觀測與調查要點

### 5.1 何時檢查 Flow Log

- 追蹤各階段（contact_address → residence_address → contract_coordinates）是否按序執行
- 監控 INSERT SQL 與 SELECT SQL 的執行成功率
- 確認批次切換邏輯（`is_last_batch` 判斷）

### 5.2 何時檢查 API Log

- 監控 Geocoding API 各批次的成功率與重試次數
- 分析 REQUEST_DENIED 或 UNKNOWN_ERROR 的發生頻率
- 評估 API quota 使用情況

### 5.3 何時檢查 Cloud Logging

- 實時監控致命錯誤（REQUEST_DENIED、UNKNOWN_ERROR）
- 追蹤各階段的狀態轉移（Notice 級別）
- 調查非預期的例外與警告

### 5.4 關鍵尋找關鍵字

- **flow_log**: `TASK_CODE`, `FLOW_NAME`, `STATUS` 進行篩選
- **api_log**: `API_Name="geocoding-api"`, `Status_Code` 分組
- **Cloud Logging**: `severity="Error"`, `log_type="flow_log"`, `log_type="api_log"`, `service="geo-data-resolver"`

---

## 附錄：相關文件

- [API_USAGE_GUIDE.md](API_USAGE_GUIDE.md) - POST /geocoding 的 payload 與回應格式
- [ARCHITECTURE.md](ARCHITECTURE.md) - 整體架構與流程設計
- [feature-geocoding-pipeline-1.md](../plan/feature-geocoding-pipeline-1.md) - 實作計畫與需求
