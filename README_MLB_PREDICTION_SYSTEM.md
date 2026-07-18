# MLB 大小分預測系統 - 完整程式碼

## 📋 專案說明

這是一個完整的 MLB 大小分預測數據抓取系統，整合了：
- MLB StatsAPI 免費資料
- OpenWeatherMap 天氣 API
- Google Sheets 自動同步
- 大小分預測模型所需的所有指標

## 🚀 快速開始

### 1. 安裝依賴

```bash
pip install gspread oauth2client pandas pytz requests scipy
```

如果需要天氣 API：
```bash
pip install openweather-client-python
```

### 2. 設定環境變數

```bash
export MLB_GOOGLE_SHEET_ID="YOUR_SPREADSHEET_ID"
export GOOGLE_CREDENTIALS_PATH="/path/to/credentials.json"
export OPENWEATHER_API_KEY="YOUR_OPENWEATHER_API_KEY"
```

### 3. 執行腳本

```bash
# 執行今日數據
python3 mlb_daily_cron_job_v2.py

# 或指定日期
python3 mlb_daily_cron_job_v2.py 2026-07-18
```

## 📊 資料表結構

### team_stats（比賽數據表）

| 欄位 | 說明 | 用途 |
|------|------|------|
| Game_ID | 比賽 ID | 唯一識別 |
| Away_Team_Name | 客隊名稱 | - |
| Home_Team_Name | 主隊名稱 | - |
| Away_Started_Pitcher_ID | 客隊先發投手 ID | 關聯投手數據 |
| Home_Started_Pitcher_ID | 主隊先發投手 ID | 關聯投手數據 |
| Park_Factor | 場地因子 | 場地調整 |
| Weather_Temperature_F | 華氏溫度 | 天氣調整 |
| Weather_Wind_Speed_MPH | 風速 | 天氣調整 |
| Weather_Wind_Deg | 風向度數 | 天氣調整 |
| Weather_Adjustment | 天氣調整係數 | 最終調整 |
| Away_Batting_OBP | 客隊上壘率 | 攻擊調整 |
| Away_Batting_SLG | 客隊長打率 | 攻擊調整 |
| Away_Batting_OPS | 客隊進攻指數 | 攻擊調整 |
| Home_Batting_OBP | 主隊上壘率 | 攻擊調整 |
| Home_Batting_SLG | 主隊長打率 | 攻擊調整 |
| Home_Batting_OPS | 主隊進攻指數 | 攻擊調整 |

### starting_pitchers（先發投手數據表）

| 欄位 | 說明 |
|------|------|
| PitcherId | 投手 ID |
| PitcherName | 投手姓名 |
| TeamName | 所屬球隊 |
| ERA | 防禦率 |
| WHIP | 每局上壘率 |
| K% | 三振率 |
| BB% | 保送率 |
| K-BB% | 淨三振率 |
| BABIP | 壘打率 |
| StrikeoutsPer9Inn | 每九局三振 |
| WalksPer9Inn | 每九局保送 |

### bullpen_record（牛棚數據表）

| 欄位 | 說明 |
|------|------|
| PitcherId | 投手 ID |
| PitcherName | 投手姓名 |
| TeamName | 所屬球隊 |
| ERA | 防禦率 |
| WHIP | 每局上壘率 |
| Saves (SV) | 救援成功 |
| Holds (HLD) | 中繼成功 |
| K% | 三振率 |
| BB% | 保送率 |
| K-BB% | 淨三振率 |

## 🎯 預測模型使用

### Lambda 計算公式

```
λ = 基礎得分 × 攻擊調整 × 投手調整 × 場地因子 × 天氣調整

基礎得分 = 4.5（聯盟平均）

攻擊調整 = (球隊 OBP / 聯盟 OBP) × (球隊 SLG / 聯盟 SLG)

投手調整 = 聯盟 ERA / 對方投手 ERA

場地因子 = 從 PARK_FACTORS 字典取得

天氣調整 = 從 Weather_Adjustment 欄位取得
```

### Python 範例

```python
def calculate_lambda(team_obp, team_slg, opponent_era, park_factor, weather_adj):
    """計算預期得分 Lambda"""
    base_runs = 4.5
    league_avg_obp = 0.320
    league_avg_slg = 0.400
    league_avg_era = 4.50
    
    attack_adjust = (team_obp / league_avg_obp) * (team_slg / league_avg_slg)
    pitcher_adjust = league_avg_era / max(opponent_era, 1.0)
    
    lambda_runs = base_runs * attack_adjust * pitcher_adjust * park_factor * weather_adj
    return max(lambda_runs, 2.0)
```

## 🌤️ 天氣 API 設定

### 取得 OpenWeatherMap API Key

1. 前往 https://openweathermap.org/api
2. 註冊免費帳號
3. 取得 API Key（免費版每月 1000 次請求）

### 測試天氣 API

```bash
curl "https://api.openweathermap.org/data/2.5/weather?q=Los Angeles,US&appid=YOUR_KEY&units=imperial"
```

## 📈 未來擴充

1. **球隊賽季打擊數據**：從累計方式取得
2. **Statcast 進階指標**：xwOBA, Barrel%, Hard Hit%
3. **傷病報告整合**：評估陣容完整性
4. **自動投注建議**：比較公平賠率與市場賠率

## ⚠️ 注意事項

1. MLB StatsAPI 可能有速率限制，腳本已加入隨機延遲
2. OpenWeatherMap 免費版每月 1000 次請求
3. Google Sheets 需要 Service Account 權限
4. 建議先在測試環境驗證再正式使用

## 📝 版本歷史

- **v2.0** (2026-07-18): 完整天氣 API 整合
- **v1.0**: 基礎賽程與投手數據抓取
