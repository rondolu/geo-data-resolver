# BigQuery Table Schemas

本文件聚焦目前流程實際使用的表格與關鍵欄位（非完整 DDL）。

## 1. `RAW_EDEP_DATASET.GEO_DATA`

用途：存放 Place Aggregate 成功記錄。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| uuid | STRING | 批次追蹤 UUID |
| cuid | STRING | 客戶識別 |
| serial_number | STRING | 案件序號 |
| contact_address | STRING | 通訊地址 |
| residence_address | STRING | 戶籍地址 |
| company_name | STRING | 公司名稱 |
| contract_longitude | STRING | 合約經度 |
| contract_latitude | STRING | 合約緯度 |
| raw_data | STRING(JSON) | 內含 `scenario_counts` |
| BQ_UPDATED_TIME | DATETIME | 更新時間 |
| PARTITION_DATE | DATE | 分區日期 |

`raw_data` 範例：

```json
{
  "scenario_counts": {
    "corporate_finance": "4",
    "commercial": "12",
    "residential": "9"
  }
}
```

## 2. `RAW_EDEP_DATASET.GEO_DATA_FAILED_RETRY_LIST`

用途：保存 Place Aggregate 失敗記錄，供後續回補。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| uuid | STRING | 批次 UUID |
| cuid | STRING | 客戶識別 |
| series_number | STRING | 失敗序號（對應 serial_number） |
| contact_address | STRING | 通訊地址 |
| residence_address | STRING | 戶籍地址 |
| tax_code | STRING | 稅號 |
| company_name | STRING | 公司名稱 |
| contract_longitude | STRING | 合約經度 |
| contract_latitude | STRING | 合約緯度 |
| api_payload_message | STRING | 失敗請求內容 |
| api_status | STRING | 失敗狀態碼或訊息 |
| BQ_UPDATED_TIME | DATETIME | 更新時間 |
| PARTITION_DATE | DATE | 分區日期 |

## 3. `TRANS_EDEP_DATASET.TMP_GEO_DATA`

用途：由 `flatten_geo_data.sql` 轉換後的下游表。

重點映射欄位：

| 欄位 | 來源 |
| --- | --- |
| contract_poi_corporate_finance | `raw_data.scenario_counts.corporate_finance` |
| contract_poi_commercial_facility | `raw_data.scenario_counts.commercial` |
| contract_poi_residential | `raw_data.scenario_counts.residential` |

備註：多數 geocoding 與通勤欄位目前由 flatten 先填 `NULL`，待 geocoding 流程補齊資料。

## 4. `RAW_EDEP_DATASET.GEOCODING`

用途：保存 Geocoding 三階段標準化結果。

| 欄位 | 型別 | 說明 |
| --- | --- | --- |
| CUID | STRING | 客戶識別 |
| SERIAL_NUMBER | STRING | 案件序號 |
| CREATED_AT | TIMESTAMP/DATETIME | 來源建立時間 |
| GEO_TYPE | STRING | `CONTACT_ADDRESS`/`RESIDENCE_ADDRESS`/`CONTRACT_COORDINATES` |
| REQUEST_ADDRESS | STRING | 輸入地址（地址型階段） |
| REQUEST_LONGITUDE | STRING | 輸入經度（座標型階段） |
| REQUEST_LATITUDE | STRING | 輸入緯度（座標型階段） |
| RESPONSE_PLACE_ID | STRING | Geocoding place id |
| RESPONSE_ADDRESS | STRING | 標準化地址 |
| RESPONSE_GLOBAL_CODE | STRING | plus code |
| RESPONSE_PLACE_TYPES | STRING | place type 清單 |
| RESPONSE_LONGITUDE | STRING | 回傳經度 |
| RESPONSE_LATITUDE | STRING | 回傳緯度 |
| RESPONSE_COUNTRY | STRING | 國家 |
| RESPONSE_CITY | STRING | 城市 |
| RESPONSE_DISTRICT | STRING | 行政區 |
| RESPONSE_WARD | STRING | 鄉鎮/里 |
| RESPONSE_STREET | STRING | 街道 |
| BQ_CREATED_TIME | DATETIME | 建立時間 |
| BQ_UPDATED_TIME | DATETIME | 更新時間 |
