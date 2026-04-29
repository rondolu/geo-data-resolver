# 1) Business Requirements

本文件依目前程式碼與 SQL 行為整理業務需求，範圍只包含已上線的流程：

- Place Aggregate 批次流程
- Geocoding 三階段流程

## 1.1 目標

- 以批次方式處理申貸相關地理資料，取得合約座標周邊 POI 計數。
- 將 POI 結果先落 RAW，再扁平化至 TRANS。
- 在 Place Aggregate 完成後，自動接續 Geocoding 三階段，補齊地址/座標標準化資料。

## 1.2 範圍

### In Scope

- `POST /` Daily 流程。
- `POST /get_data_range` 日期區間流程。
- `POST /geocoding` 三階段 geocoding 流程（contact/residence/contract）。
- failed-retry 回補與 flatten。
- 完成後匿名化通知。

### Out of Scope

- Text Search、Routes、Place Details 多 API 串接（目前程式未實作在主流程）。
- 非 `RAW_EDEP_DATASET` / `TRANS_EDEP_DATASET` 的下游處理細節。

## 1.3 Business Requirements

### BR-01 觸發模式

- 系統需支援 Daily 與 Range 兩種進件方式。
- Pub/Sub Push 訊息成功處理時，路由需回 `204`。

### BR-02 來源資料載入與去重

- Daily 模式使用 `get_geo_query_data.sql`。
- Range 模式使用 `get_geo_query_data_range.sql`。
- Daily 查詢需排除：
  - 已存在 `RAW_EDEP_DATASET.GEO_DATA` 的 `serial_number`
  - 已存在 `GEO_DATA_FAILED_RETRY_LIST` 的 `series_number`

### BR-03 POI 三情境處理規則

- 每筆資料必須依序處理三個情境：
  - `corporate_finance`
  - `residential`
  - `commercial`
- 若任一情境 API 例外：
  - 該筆記錄寫入 failed-retry 表
  - 該筆不得寫入 RAW GEO_DATA
- 若僅為座標無效，該情境 `count="null"`，不中斷整筆處理。

### BR-04 批次回呼

- 非最後一批需發布 recall 訊息觸發下一批。
- 最後一批需進入 post-batch 流程。

### BR-05 post-batch 規則

- 先載入 failed-retry 視窗資料並回補。
- 執行 `flatten_geo_data.sql`。
- flatten 成功後才可發布 geocoding 第一階段啟動訊息。

### BR-06 Geocoding 三階段接續

- 階段順序必須固定為：
  1. `contact_address`
  2. `residence_address`
  3. `contract_coordinates`
- 每階段 `batch_number=1` 時，先執行對應 update SQL 再執行 query SQL。
- 每階段非最後一批需發布同階段 recall。
- 最終階段完成後發布 anonymization 訊息。

### BR-07 Geocoding 例外處理

- `REQUEST_DENIED` 與 `UNKNOWN_ERROR` 視為致命錯誤，需中止該批流程。
- 其他 Geocoding 例外可跳過單筆，持續處理後續資料。

## 1.4 成功標準

- AC-01：Daily/Range 都可完整觸發並回傳合理狀態。
- AC-02：POI 三情境符合「任一情境例外則整筆不寫 RAW」規則。
- AC-03：最後一批會依序完成 failed-retry、flatten、geocoding 啟動。
- AC-04：Geocoding 三階段能自動串接，並在最終階段送出匿名化訊息。

## 1.5 風險與邊界

- SQL 規則高度依賴上游資料品質（例如字串 `"null"` 與實際 NULL 混用）。
- failed-retry 視窗策略屬時間相依邏輯，補歷史資料時需關注視窗設定。
- Geocoding 階段若遇致命狀態，會中止流程，不會自動降級。
