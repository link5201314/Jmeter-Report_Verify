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

## Prompt 01：優化檢查邏輯

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
