// Report data stored separately to avoid template literal conflicts
var reports = {
    "MLB預測模型": [
        {
            "id": "hobie-model",
            "title": "HOBIE 模型深度研究",
            "date": "2026-07-15",
            "tags": ["模型", "預測", "HOBIE"],
            "content": "# HOBIE 模型深度研究報告\n\n## 一、基本介紹\n\n**HOBIE**（**H**olistic **O**utcomes **B**aseball **I**nsight **E**ngine）是由 **Brian Burkhard** 開發的 MLB 賽季勝場預測模型。\n\n- **開發者背景**：Brian Burkhard，博士學位，專業領域為優化模型與心理屬性評估\n- **首次發表**：2022 年 4 月 6 日 Medium 文章\n- **命名由來**：致敬 Hobie Landrith——1961 年紐約大都會隊擴編選秀第一順位\n\n## 二、核心設計理念\n\n> 識別上一個賽季中不可重複事件（即「運氣」）對勝場總數的影響程度，然後根據名單變動確定這些因素將如何改變下一賽季的基準。\n\n### 關鍵思路：\n\n1. **去除「群聚運氣」（Cluster Luck）**：調整 OBP/SLG/ISO 等數據，回歸到可重複的真實表現\n2. **考慮名單變動**：老化曲線、交易、自由球員簽訂\n3. **整體性方法（Holistic）**：綜合考量攻擊、投球、牛棚、防守等多維度\n\n## 三、模型績效\n\n| 指標 | HOBIE | FanGraphs | PECOTA |\n|------|-------|-----------|--------|\n| **MAE** | **最低** | 低 | 中 |\n| **RMSE** | **最低** | 低 | 中 |\n| **投注命中率** | **68%** | ~50% | ~47% |\n| **2024 戰績** | **14-3** | - | - |\n\n## 四、結論\n\nHOBIE 的核心競爭力在於徹底去除運氣成分，聚焦可重複的真實表現，並前瞻性地考量名單變動。\n\n---\n\n## 附錄：mlb_daily_cron_job.py 修改建議完整版\n\n### 一、現有程式分析\n\n你的 `mlb_daily_cron_job.py` 已經成功抓取：\n- ✅ 每日賽程與比分\n- ✅ 先發投手 ID 與賽季數據（ERA, WHIP, K%, BB%）\n- ✅ 先發投手當場數據（IP, H, ER, K, BB）\n\n### 二、缺少的資料\n\n| 類別 | 用途 | 缺口 |\n|------|------|------|\n| **牛棚數據** | 評估球隊整體投球實力 | ❌ 尚未抓取 |\n| **球隊打擊數據** | 計算攻擊調整（OBP/SLG/OPS） | ❌ 僅有當場數據 |\n| **場地因子** | 調整主場優劣勢 | ⚠️ 需要手動維護 |\n| **天氣數據** | 溫度/風向調整 | ❌ 尚未整合 |\n\n### 三、建議修改方案\n\n我已建立完整建議版本：`mlb_daily_cron_job_v2.py`\n\n主要新增功能：\n1. **牛棚投手數據抓取**：從 boxscore 提取 bullpen IDs，逐一抓取賽季數據\n2. **球隊打擊數據**：從 boxscore 的 teamStats.batting 取得當場數據\n3. **場地因子**：內建 30 支球隊球場因子映射表\n4. **天氣 API 整合**：OpenWeatherMap 免費版，取得溫度/風速/風向\n5. **Google Sheets 結構**：新增 starting_pitchers 與 bullpen_record 分頁\n\n### 四、大小分預測模型所需資料\n\n| 資料 | 欄位 | 用途 |\n|------|------|------|\n| 先發投手 | ERA, WHIP, K%, BB%, K-BB% | 計算投手調整 |\n| 牛棚投手 | SV, HLD, ERA, WHIP, GF | 評估後援實力 |\n| 球隊打擊 | OBP, SLG, OPS, HR, R | 計算攻擊調整 |\n| 場地因子 | 1.00 (聯盟平均) | 場地調整 |\n| 天氣數據 | 溫度/風速/風向 | 天氣調整 |\n\n### 五、使用方式\n\n```bash\n# 執行新版腳本\npython3 mlb_daily_cron_job_v2.py 2026-07-18\n\n# 資料將寫入 Google Sheets 三個分頁：\n# - team_stats: 比賽數據 + 球隊打擊 + 場地因子 + 天氣數據\n# - starting_pitchers: 先發投手賽季數據\n# - bullpen_record: 牛棚投手賽季數據\n```\n\n### 六、天氣 API 設定\n\n1. 前往 https://openweathermap.org/api 註冊免費帳號\n2. 取得 API Key（免費版每月 1000 次請求）\n3. 設定環境變數：\n   ```bash\n   export OPENWEATHER_API_KEY=\"YOUR_API_KEY\"\n   ```\n\n### 七、Lambda 計算公式\n\n```\nλ = 基礎得分 × 攻擊調整 × 投手調整 × 場地因子 × 天氣調整\n\n基礎得分 = 4.5（聯盟平均）\n攻擊調整 = (球隊 OBP / 聯盟 OBP) × (球隊 SLG / 聯盟 SLG)\n投手調整 = 聯盟 ERA / 對方投手 ERA\n場地因子 = 從 PARK_FACTORS 字典取得\n天氣調整 = 從 Weather_Adjustment 欄位取得\n```\n"
        },
        {
            "id": "pitching-metrics",
            "title": "投球指標與預測模型公式",
            "date": "2026-07-15",
            "tags": ["投球", "指標", "公式"],
            "content": "# 投球指標與預測模型公式\n\n## 一、投球指標與勝率相關性排名\n\n| 排名 | 指標 | 與勝率相關性 |\n|------|------|-------------|\n| 1 | **Run Differential** | ~0.90 |\n| 2 | **ERA** | -0.88 |\n| 3 | **Opponent OPS** | -0.86 |\n| 4 | **LOB%** | ~0.70+ |\n| 5 | **Pitching WAR** | ~0.65+ |\n\n## 二、賽季勝場預測公式\n\n### Pythagorean Expectation\n\n勝率 = RS^2 / (RS^2 + RA^2)\n\n現代改良版（指數 1.83）：\n\n勝率 = RS^1.83 / (RS^1.83 + RA^1.83)\n\n### 預期勝場計算\n\n預期勝場 = 162 x 勝率\n\n## 三、單場比分預測公式\n\n### Lambda 計算\n\nlambda = 基礎得分 x 攻擊調整 x 投手調整 x 場地因子 x 天氣因子\n\n### Poisson 分佈\n\nP(X = k) = (e^-lambda x lambda^k) / k!\n\n## 四、Python 實作範例\n\n```python\nfrom scipy.stats import poisson\n\ndef predict_game(lambda_home, lambda_away):\n    win_prob_home = 0\n    for i in range(15):\n        for j in range(i):\n            win_prob_home += poisson.pmf(i, lambda_home) * poisson.pmf(j, lambda_away)\n    return win_prob_home\n```\n"
        }
    ],
    "投手分析": [
        {
            "id": "multi-role-pitcher",
            "title": "多功能投手角色評估",
            "date": "2026-07-15",
            "tags": ["投手", "Swingman", "角色"],
            "content": "# 多功能投手角色評估\n\n## 一、MLB 投手的六大角色分類\n\n| 角色 | 定義 | 典型局數 |\n|------|------|----------|\n| **先發投手 (SP)** | 每場開局投球 | 5-7 局 |\n| **開路者 (Opener)** | 先發 1-2 局後換人 | 1-2 局 |\n| **長中繼 (Long Reliever)** | 先發早退時補位 | 3-5 局 |\n| **中繼投手** | 中段局數接手 | 1-2 局 |\n| **布局投手 (Setup Man)** | 第九局前保護領先 | 1 局 |\n| **終結者 (Closer)** | 最後一局守住勝利 | 1 局 |\n\n## 二、為什麼不能直接用 ERA 比較？\n\nBill James 在 1977 年的 SABR 研究證明：**救援角色的 ERA 天生比先發低 0.25-0.50 分**。\n\n### 三大原因：\n\n1. **已有人出局** - 救援投手通常帶著 1-2 出局上場\n2. **只面對打者一次** - 先發投手每場面對打序 2-3 次\n3. **全力投球** - 救援投手知道只投 1 局\n\n## 三、分離式評估方法\n\n綜合 SIERA = w_SP x SIERA_SP + w_RP x SIERA_RP\n\n其中：\n- w_SP = 先發局數 / 總局數\n- w_RP = 救援局數 / 總局數\n\n## 四、評估步驟\n\n1. **確認角色分佈** - 先發/救援場次比例\n2. **分別計算技能指標** - SIERA/xFIP/K-BB%\n3. **檢查 Statcast 品質** - Stuff+/SwStr%\n4. **計算加權綜合評分**\n5. **評估角色適應力**\n"
        },
        {
            "id": "pitcher-recent-form",
            "title": "先發投手近況評估方法",
            "date": "2026-07-15",
            "tags": ["投手", "近期表現", "評估"],
            "content": "# 先發投手近況評估方法\n\n## 一、為什麼「近 30 天」不合理？\n\n```\n先發投手每 5 天出賽一次\n30 天 = 約 6 場先發 = 約 30-40 IP\n```\n\n| 指標 | 穩定所需最低 IP | 30 天 IP | 結論 |\n|------|----------------|---------|------|\n| **SIERA** | >= 40 IP | 30-40 IP | 邊緣 |\n| **xFIP** | >= 30 IP | 30-40 IP | 勉強 |\n| **K-BB%** | >= 50 IP | 30-40 IP | 不足 |\n\n## 二、正確的評估方法：多層級加權框架\n\n| 數據來源 | 建議權重 |\n|---------|---------||\n| **整季 SIERA/xFIP** | **40%** |\n| **Statcast 品質指標** | **25%** |\n| **近 10 場先發（~50 IP）** | **20%** |\n| **生涯數據（最後 3 年）** | **15%** |\n\n## 三、為什麼是「近 10 場」而不是「近 30 天」？\n\n```\n近 10 場 = 約 50 天 = 約 50-60 IP\n```\n\n- 超過 40 IP 門檻\n- 單場波動影響降至 ~10%\n- 能反映真正的近期狀態趨勢\n\n## 四、Python 實作\n\n```python\ndef evaluate_pitcher(pitcher_data):\n    season_weight = 0.40\n    statcast_weight = 0.25\n    recent_weight = 0.20\n    career_weight = 0.15\n    \n    weighted_siera = (\n        season_weight * pitcher_data['season_siera'] +\n        recent_weight * pitcher_data['recent_10_siera'] +\n        career_weight * pitcher_data['career_siera']\n    )\n    \n    return weighted_siera\n```\n"
        }
    ],
    "投注策略": [
        {
            "id": "mlb-betting-strategy",
            "title": "台灣運彩 MLB 玩法分析",
            "date": "2026-07-15",
            "tags": ["投注", "台灣運彩", "策略"],
            "content": "# 台灣運彩 MLB 玩法分析\n\n## 一、三大玩法的獲勝率比較\n\n| 玩法 | 平均命中率 | 平均賠率 | 期望值(EV) |\n|------|-----------|---------|------------|\n| **大小分** | **50-55%** | **1.85-1.95** | **最佳** |\n| **獨贏** | 45-55% | 1.70-2.30 | 偏低 |\n| **讓分盤** | 40-50% | 1.55-2.10 | 偏高風險 |\n\n## 二、為什麼大小分最有優勢？\n\n1. **數據最透明** - 先發投手 SIERA、球隊 xwOBA、場地因子\n2. **莊家難以完全定價** - 相比獨贏，受更多變數影響\n3. **波動性較低** - 總分是累加的，隨機性較小\n4. **樣本量大** - 162 場 x 30 隊 = 4,860 場/年\n\n## 三、推薦投注順序\n\n| 排名 | 玩法 | 推薦理由 | 預期命中率 |\n|------|------|---------|------------|\n| 1 | **大小分** | 數據最透明 | **52-55%** |\n| 2 | **[1-5局] 獨贏** | 排除牛棚變數 | **55-60%** |\n| 3 | **獨贏** | 簡單易懂 | 48-52% |\n\n## 四、系統化投注策略\n\n### 特定球隊 x 特定星期（CSDA 實證）\n\n- **條件**：洋基/小熊/金鶯 + 星期四\n- **樣本**：61 場\n- **戰績**：44 勝 17 敗\n- **勝率**：**72.1%**\n- **ROI**：**39.7%**\n\n### 先發投手 SIERA 差距法\n\n```\n當先發投手 SIERA 差距 >= 0.80：\n  -> 押 SIERA 較低的那隊獨贏\n  -> 命中率約 58-62%\n```\n"
        },
        {
            "id": "betting-tracker",
            "title": "投注紀錄系統",
            "date": "2026-07-15",
            "tags": ["紀錄", "系統", "EV"],
            "content": "# 投注紀錄系統\n\n## 一、系統架構\n\n```\n投注紀錄系統/\n  bet_tracker.py          # Python 程式\n  bets.csv                # 原始數據\n  dashboard.html          # 視覺化儀表板\n  README.md               # 使用說明\n```\n\n## 二、需要紀錄的欄位\n\n| 欄位 | 說明 | 範例 |\n|------|------|------|\n| `date` | 比賽日期 | 2026-07-15 |\n| `home_team` | 主隊 | Dodgers |\n| `away_team` | 客隊 | Yankees |\n| `bet_type` | 玩法 | Over/Under |\n| `pick` | 選擇 | Over 8.5 |\n| `odds` | 賠率 | 1.85 |\n| `stake` | 下注金額 | 1000 |\n| `model_probability` | 模型預測概率 | 0.58 |\n| `result` | 結果 | Win/Loss |\n| `profit_loss` | 盈虧 | +850/-1000 |\n\n## 三、期望值計算\n\nEV = (勝率 x 贏的钱) - (敗率 x 押钱)\n\n### 範例：55% 命中率，賠率 1.85\n\n```\n每場押 1000 元，500 場：\n  贏 275 場，輸 225 場\n  贏的钱：275 x 1850 = 508,750\n  押的钱：500 x 1000 = 500,000\n  淨獲利：+8,750 元\n```\n\n## 四、資金管理\n\n- 每場投注不超過總資金的 **3-5%**\n- 連續輸 5 場 -> 降碼到 50%\n- 連續贏 5 場 -> 升碼到 150%\n"
        }
    ],
    "程式碼": [
        {
            "id": "mlb-cron-job-v2",
            "title": "MLB 大小分預測 - 完整程式碼 v2.0",
            "date": "2026-07-18",
            "tags": ["程式碼", "cron", "天氣API"],
            "content": "# MLB 大小分預測系統 - 完整程式碼 v2.0\n\n## 📋 專案說明\n\n這是一個完整的 MLB 大小分預測數據抓取系統，整合了：\n- MLB StatsAPI 免費資料\n- OpenWeatherMap 天氣 API\n- Google Sheets 自動同步\n- 大小分預測模型所需的所有指標\n\n## 🚀 快速開始\n\n### 1. 安裝依賴\n\n```bash\npip install gspread oauth2client pandas pytz requests scipy\n```\n\n如果需要天氣 API：\n```bash\npip install openweather-client-python\n```\n\n### 2. 設定環境變數\n\n```bash\nexport MLB_GOOGLE_SHEET_ID=\"YOUR_SPREADSHEET_ID\"\nexport GOOGLE_CREDENTIALS_PATH=\"/path/to/credentials.json\"\nexport OPENWEATHER_API_KEY=\"YOUR_OPENWEATHER_API_KEY\"\n```\n\n### 3. 執行腳本\n\n```bash\n# 執行今日數據\npython3 mlb_daily_cron_job_v2.py\n\n# 或指定日期\npython3 mlb_daily_cron_job_v2.py 2026-07-18\n```\n\n## 📊 資料表結構\n\n### team_stats（比賽數據表）\n\n| 欄位 | 說明 | 用途 |\n|------|------|------|\n| Game_ID | 比賽 ID | 唯一識別 |\n| Away_Team_Name | 客隊名稱 | - |\n| Home_Team_Name | 主隊名稱 | - |\n| Away_Started_Pitcher_ID | 客隊先發投手 ID | 關聯投手數據 |\n| Home_Started_Pitcher_ID | 主隊先發投手 ID | 關聯投手數據 |\n| Park_Factor | 場地因子 | 場地調整 |\n| Weather_Temperature_F | 華氏溫度 | 天氣調整 |\n| Weather_Wind_Speed_MPH | 風速 | 天氣調整 |\n| Weather_Wind_Deg | 風向度數 | 天氣調整 |\n| Weather_Adjustment | 天氣調整係數 | 最終調整 |\n| Away_Batting_OBP | 客隊上壘率 | 攻擊調整 |\n| Away_Batting_SLG | 客隊長打率 | 攻擊調整 |\n| Away_Batting_OPS | 客隊進攻指數 | 攻擊調整 |\n| Home_Batting_OBP | 主隊上壘率 | 攻擊調整 |\n| Home_Batting_SLG | 主隊長打率 | 攻擊調整 |\n| Home_Batting_OPS | 主隊進攻指數 | 攻擊調整 |\n\n### starting_pitchers（先發投手數據表）\n\n| 欄位 | 說明 |\n|------|------|\n| PitcherId | 投手 ID |\n| PitcherName | 投手姓名 |\n| TeamName | 所屬球隊 |\n| ERA | 防禦率 |\n| WHIP | 每局上壘率 |\n| K% | 三振率 |\n| BB% | 保送率 |\n| K-BB% | 淨三振率 |\n| BABIP | 壘打率 |\n| StrikeoutsPer9Inn | 每九局三振 |\n| WalksPer9Inn | 每九局保送 |\n\n### bullpen_record（牛棚數據表）\n\n| 欄位 | 說明 |\n|------|------|\n| PitcherId | 投手 ID |\n| PitcherName | 投手姓名 |\n| TeamName | 所屬球隊 |\n| ERA | 防禦率 |\n| WHIP | 每局上壘率 |\n| Saves (SV) | 救援成功 |\n| Holds (HLD) | 中繼成功 |\n| K% | 三振率 |\n| BB% | 保送率 |\n| K-BB% | 淨三振率 |\n\n## 🎯 預測模型使用\n\n### Lambda 計算公式\n\n```\nλ = 基礎得分 × 攻擊調整 × 投手調整 × 場地因子 × 天氣調整\n\n基礎得分 = 4.5（聯盟平均）\n攻擊調整 = (球隊 OBP / 聯盟 OBP) × (球隊 SLG / 聯盟 SLG)\n投手調整 = 聯盟 ERA / 對方投手 ERA\n場地因子 = 從 PARK_FACTORS 字典取得\n天氣調整 = 從 Weather_Adjustment 欄位取得\n```\n\n### Python 範例\n\n```python\ndef calculate_lambda(team_obp, team_slg, opponent_era, park_factor, weather_adj):\n    base_runs = 4.5\n    league_avg_obp = 0.320\n    league_avg_slg = 0.400\n    league_avg_era = 4.50\n    \n    attack_adjust = (team_obp / league_avg_obp) * (team_slg / league_avg_slg)\n    pitcher_adjust = league_avg_era / max(opponent_era, 1.0)\n    \n    lambda_runs = base_runs * attack_adjust * pitcher_adjust * park_factor * weather_adj\n    return max(lambda_runs, 2.0)\n```\n\n## 🌤️ 天氣 API 設定\n\n### 取得 OpenWeatherMap API Key\n\n1. 前往 https://openweathermap.org/api 註冊免費帳號\n2. 取得 API Key（免費版每月 1000 次請求）\n3. 設定環境變數：\n   ```bash\n   export OPENWEATHER_API_KEY=\"YOUR_API_KEY\"\n   ```\n\n## 💻 完整程式碼\n\n完整程式碼請見 GitHub Repository：\n\n👉 [**mlb_daily_cron_job_v2.py**](https://github.com/kidd221122-hub/mlb_report/blob/main/mlb_daily_cron_job_v2.py)\n\n或直接查看整個專案：\n\n👉 [**kidd221122-hub/mlb_report**](https://github.com/kidd221122-hub/mlb_report)\n"
        }
    ]
};
