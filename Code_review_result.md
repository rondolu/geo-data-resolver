**程式碼審查報告**

## Overall
- Status: Pass⚠️
- Reason: 本次以 Folder 為分母完成全專案 Python/SQL style 與 security 審查（Coverage=100%），未發現 MUST 違規；仍有 SHOULD 項目（`print(...)` 長期日誌）待改善。
- 觸發到的場景（若有）。: 無（使用者描述未精確匹配第 7 節場景關鍵字）。

## Scope/Exclude

- Scope 來源：使用者指定 `Follow instructions in #prompt:code-review.prompt.md`，以 repo 全量檔案審查。
- In Scope：Python（`.py`）與 BigQuery SQL（`.sql`）。
- Exclude：非 `.py` / `.sql` 檔案（文件、設定、JSON、Shell 等）。
- Exclude Rules：`**/*` 中僅納入 `*.py`、`*.sql`。
- Exclude Reasons：
  - `OUT_OF_SCOPE`: 非 Python/SQL 檔案，不屬本次 style/security 審查分母。
- Excluded Count：32

## Coverage
- Denominator Type: Folder
- Total_files: 49
- Reviewed_files: 49
- Unreviewed files: 0
- Coverage: 49/49
- Coverage Reason: 以檔案系統 metadata 可靠枚舉（AllFiles=81），依副檔名規則排除後分母 N=49；逐檔完成規則掃描與重點程式碼檢視，R=49、U=0，且驗證 N=R+U。

## Rules

### Python 規則

| 規則類別 | 規則等級 | 狀態 | 詳細說明與修正建議 |
| :--- | :---: | :---: | :--- |
| **[Python][Formatting: 4 spaces、禁止 Tab]** | MUST | Pass✅ | 未發現 Tab 縮排；Python 檔案目前符合 4 spaces 要求。 |
| **[Python][例外處理：禁止吞掉例外 except Exception: pass]** | MUST | Pass✅ | 未發現 `except Exception: pass`。 |
| **[Python][imports 分段與 wildcard import 禁止]** | MUST | Pass✅ | 未發現 `from x import *`。 |
| **[Python][print 不作長期日誌]** | SHOULD | Warning⚠️ | 仍存在 `print(...)`（如 `application/batch_process_service.py`、`utils/metrics.py`）；建議改為 custom-log。 |

### SQL 規則

| 規則類別 | 規則等級 | 狀態 | 詳細說明與修正建議 |
| :--- | :---: | :---: | :--- |
| **[SQL][BigQuery Standard SQL 與 JOIN ON 明確性]** | MUST | Pass✅ | 檢視 `.sql` 檔案未發現 Legacy SQL；JOIN 具明確 ON 條件。 |
| **[SQL][避免 SELECT *]** | SHOULD | Pass✅ | 未發現有效查詢語句使用 `SELECT *`（僅註解內容）。 |
| **[SQL][參數化與可讀性]** | SHOULD | Pass✅ | 未發現新增的字串拼接 SQL 可變條件風險。 |

### Checkmarx 規則

| 規則類別 | 規則等級 | 狀態 | 詳細說明與修正建議 |
| :--- | :---: | :---: | :--- |
| **[Checkmarx][Information Exposure: 禁止在回應包含 str(e)]** | MUST | Pass✅ | 未發現目前 API 回應 payload 直接回傳 `str(e)` 的新增風險。 |
| **[Checkmarx][Logging Security: Exception/Error/Warning 走 custom-log]** | MUST | Pass✅ | 主要例外路徑維持 `_logger.log_text(...)`。 |
| **[Checkmarx][Transmission: SSL 驗證]** | MUST | Pass✅ | 透過環境變數控制 SSL 驗證，符合直接通過條件。 |
| **[Checkmarx][Flask Header 規則（HSTS/CSP）]** | MUST | Pass✅ | 偵測 Flask 且 `app = Flask(__name__)` 建立於 function 內，依規範直接通過。 |
| **[Checkmarx][print 做長期日誌]** | SHOULD | Warning⚠️ | 發現 `print(...)`，建議收斂為 custom-log 以符合長期稽核一致性。 |

## 審查後續流程

### 1) 結尾 CTA (Call to Action)

- 本次無 Fail❌，因此未提供 ` ```diff ` 修正區塊。
- 若要繼續優化 Warning⚠️（例如 `print(...)` 改為 custom-log），請先更新程式碼後再執行 `/code-review` 驗證。
