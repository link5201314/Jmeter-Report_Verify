# Prompt 演進手冊

此專案在解決快速檢驗Jmeter報告的90百分位反應時間與交易量是否達滿足定義的效能標準。
本文件記錄專案透過與AI協作的過程逐步實現視窗應用程式功能。

## 共同的介面品質標準

每份 Prompt 都已包含以下原則：

- 保留原本 Playwright 核心邏輯，先拆成可重複使用的函式，再接 UI。
- 長時間任務不能阻塞畫面，並要有進度、執行狀態、錯誤訊息與取消機制。
- 介面使用繁體中文，有明確層級、一致間距、無障礙對比與響應式佈局。
- 不把密碼、Cookie 或 token 寫死在程式碼。
- 不用假資料假裝功能完成；空狀態、載入、成功、失敗都要能看見。
- 資料儲存只在各 Prompt 明確要求時加入，且只能使用 CSV、XLSX 或 SQLite；不得使用 Firebase、Supabase 或其他雲端資料庫。
- 不值得保留的操作型資料只顯示在當次介面，不為了展示技術而建立資料庫。
- 產生完整可執行程式、套件說明、執行指令、README 與基本測試。

## 專案初始狀態

一開始先提供了jmeter_report、verify_config資料夾，並放置一份Jmeter Html報告，與一份csv檔案格式的verify_config，
並撰寫一個sample程式，透過playwright讀取本地Jmeter Html報告的表格數據，與讀取csv格式的verify_config，
並將兩塊資料都存入pandas，並利用兩組df數據進行一個邏輯檢查。

---

## Prompt 01：優化檢查邏輯(規則表達式匹配label)

```text
# 現階段程式邏輯
verify_result這個方法會使用選定的verify_config的標準(df_config)來檢查jmeter_report的內容(df_report)

但jmeter_report的label命名規則為[script_name]-[step]_.*，實際範例如下：
CAR_03-00_01_認證
CAR_03-01_新領編配
CAR_03-02_輸入汽機車領牌條碼
CAR_03-02-1_查詢
CAR_03-03_1_1_確認視窗
CAR_03-03_1_2_確認視窗
CAR_03-03_2_1_檢查結果

即step的規則表達式為(?<=^CAR_03-)[0-9_\-]+(?=_[^0-9_])，
也就是一個script_name裡面會有多個step

# 程式修改目標
因verify_config(參考core_PT_1.csv)，裡面只會定義script_name，
所以verify_result裡面的邏輯要改成
1. 所有label開頭符合script_name的項目都要滿足
actual_pct_90th < expected_pct_90th
2. label開頭符合script_name的項目取step編號最大的pass_cnt作為actual_pass > expected_pass的判斷標準，
也就是「CAR_03-03_2_1_檢查結果」才是CAR_03這個腳本會去取pass_cnt的項目
3. 不要發現一個錯誤就立刻return結束verify_result，要完整檢查並將失敗的項目保存到list中
4. 必要時可調整函數名稱

# 分析時請不要嘗試去讀取jmeter_report報告的實際內容，直接參考practice3.py的程式邏輯即可

```

## Prompt 02：優化檢查邏輯(增加seq、final、single三種策略選擇)

```text
# 腳色：你是資深 Python 應用工程師。請直接參考目前專案並依任務目標繼續改進與優化程式。

# 任務目標：

## 請先閱讀現有程式(現有核心程式：main.py)、README.md

## 然後我已經手動先修改了verify_config/core_PT_1.csv檔案，添加了一個新的欄位「name_rule」

##「name_rule」只會有三種值[seq、final、single]，
這三種欄位將決定verify_results函式在對不同的script_name進行actual_pass < expected_pass檢驗時所採用的策略，
說明如下
- seq: 如果該欄位是這個值，那麼就採目前verify_results原本的邏輯
- final: 每個script_name的所有步驟中，一定要包含一個script_name-<Final>.*的步驟，將採用此項目的數值作為該script_name的actual_pass
- single：該script_name都只會有一個步驟，所以只要找到唯一的script_name.*項目(也就是以script_name開頭即可)，
就採用此項目的數值作為該script_name的actual_pass

# 無論「name_rule」採用哪種策略，都應該只能match到一個目標，如果存在match一個以上，也要視作失敗，但錯誤訊息應該要跟一個也match不到有所需別

## 這個新的欄位並不影響actual_pct_90th < expected_pct_90th原本的檢驗邏輯


# 注意事項：請直接修改或建立完整檔案，不要只給範例片段或偽程式碼。同時更新 pyproject.toml 與 README，提供 uv 安裝/執行指令，並加入對核心函式的基本測試。完成後請實際執行語法檢查與 smoke test，回報修改檔案、執行方法與驗收結果。

```
