# Geo Data Resolver API Usage Guide

## 1. API 一覽

- `POST /`
  - 啟動 Daily Place Aggregate 批次。
- `POST /get_data_range`
  - 啟動 Range Place Aggregate 批次。
- `POST /geocoding`
  - 啟動或回呼 Geocoding 三階段批次。

## 2. 通用規則

- `Content-Type: application/json`
- 若請求為 Pub/Sub push 格式，且處理成功，回應為 `204`。
- 一般 HTTP 觸發成功時，回 `200` 並帶 JSON payload。

## 3. `POST /`

### 3.1 用途

啟動 Daily 模式批次。

### 3.2 請求範例

```bash
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 3.3 成功回應範例

```json
{
  "status": "processing",
  "message": "Geo-data-resolver batch 1 completed, next batch triggered",
  "total_records": 500,
  "the_batch_result": {
    "success_count": 1500,
    "error_count": 12,
    "skipped_count": 0,
    "processed_references": []
  },
  "pubsub_message_id": "..."
}
```

或在最後一批回：

```json
{
  "status": "completed",
  "message": "All batches completed at batch 3",
  "all_batch_records": 488,
  "the_batch_result": {
    "success_count": 1464,
    "error_count": 5,
    "skipped_count": 0,
    "processed_references": []
  }
}
```

## 4. `POST /get_data_range`

### 4.1 用途

以日期區間啟動批次。

### 4.2 請求主體

```json
{
  "start_date": "2026-04-01",
  "end_date": "2026-04-03"
}
```

### 4.3 驗證規則

- `start_date` 與 `end_date` 缺一不可。
- 缺少欄位會回 `400 validation_error`。

## 5. `POST /geocoding`

### 5.1 用途

執行 geocoding 階段或處理同階段 recall。

### 5.2 請求主體（一般模式）

```json
{
  "processing_params": {
    "task_type": "contact_address",
    "batch_number": 1
  }
}
```

### 5.3 `task_type` 合法值

- `contact_address`
- `residence_address`
- `contract_coordinates`

### 5.4 成功回應範例

```json
{
  "status": "processing",
  "task_type": "contact_address",
  "batch_number": 1,
  "total_records": 500,
  "the_batch_result": {
    "success_count": 472,
    "error_count": 9,
    "skipped_count": 19,
    "processed_references": []
  },
  "pubsub_message_id": "..."
}
```

最後一批：

```json
{
  "status": "completed",
  "task_type": "contract_coordinates",
  "batch_number": 2,
  "total_records": 48,
  "the_batch_result": {
    "success_count": 45,
    "error_count": 1,
    "skipped_count": 2,
    "processed_references": []
  }
}
```

## 6. Pub/Sub Push payload 形狀

```json
{
  "message": {
    "data": "<base64-encoded-json>"
  }
}
```

Base64 內可對應以下 message type：

- Place Aggregate
  - `daily_recall`
  - `range_recall`
- Geocoding
  - `geocoding_stage_start`
  - `daily_recall`（含 `task_type`，代表同階段下一批）

## 7. 錯誤回應

統一格式：

```json
{
  "status": "error",
  "error_type": "validation_error",
  "message": "...",
  "timestamp": "2026-04-07T12:34:56.000000"
}
```

常見狀態碼：

- `400`：payload 不完整或格式不符。
- `500`：未預期錯誤。
- `204`：Pub/Sub Push 成功處理（無回應 body）。
