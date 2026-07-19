#!/usr/bin/env python3
# /// script
# dependencies = [
#     "gspread",
#     "oauth2client",
#     "pandas",
#     "pytz",
#     "requests",
#     "scipy",
#     "openweather-client-python"
# ]
# ///

"""
MLB Daily Cron Job - 大小分預測完整版
======================================

功能：
1. 抓取每日賽程與先發投手數據
2. 抓取球隊打擊數據（從 boxscore 取得）
3. 抓取牛棚投手數據
4. 抓取天氣數據（OpenWeatherMap API）
5. 計算預測模型所需的 λ 值
6. 寫入 Google Sheets 供預測模型使用

作者：Edith (MLB Prediction Model)
日期：2026-07-18
版本：2.0 - 完整天氣 API 整合版
"""

import datetime
import random
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import pytz
import requests
import sys
import json
import os

# ==============================================================================
# 配置區
# ==============================================================================

# Google Sheets 配置
TARGET_SPREADSHEET_ID = os.environ.get('MLB_GOOGLE_SHEET_ID', 'YOUR_SPREADSHEET_ID_HERE')
GOOGLE_CREDENTIALS_FILE = os.environ.get('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

# OpenWeatherMap API 配置（免費版）
OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', 'YOUR_API_KEY_HERE')
OW_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

# MLB API 配置
MLB_BASE_URL = "https://statsapi.mlb.com/api/v1"

# 場地因子（2024-2025 賽季平均）
PARK_FACTORS = {
    "Coors Field": 1.15,        # Colorado - 極度有利打者
    "Great American Ball Park": 1.08,  # Cincinnati
    "Guaranteed Rate Field": 1.07,    # Chicago White Sox
    "Kauffman Stadium": 1.06,         # Kansas City
    "Comerica Park": 1.05,            # Detroit
    "Rogers Centre": 1.04,            # Toronto
    "Minute Maid Park": 1.03,         # Houston
    "Globe Life Field": 1.03,         # Texas
    "Angel Stadium": 1.02,            # LA Angels
    "Oakland Coliseum": 1.01,         # Oakland
    "T-Mobile Park": 1.00,            # Seattle
    "Tropicana Field": 0.99,          # Tampa Bay
    "Fenway Park": 0.98,              # Boston
    "Yankee Stadium": 0.97,           # NY Yankees
    "Camden Yards": 0.96,             # Baltimore
    "Citizens Bank Park": 0.95,       # Philadelphia
    "Truist Park": 0.94,              # Atlanta
    "loanDepot park": 0.93,           # Miami
    "Wrigley Field": 0.92,            # Chicago Cubs
    "American Family Field": 0.91,    # Milwaukee
    "Busch Stadium": 0.90,            # St. Louis
    "PNC Park": 0.89,                 # Pittsburgh
    "Oracle Park": 0.88,              # San Francisco
    "Petco Park": 0.87,               # San Diego
    "Dodger Stadium": 0.86,           # LA Dodgers
    "Chase Field": 0.85,              # Arizona
}

# 聯盟平均基準值
LEAGUE_AVG_RUNS = 4.5
LEAGUE_AVG_OBP = 0.320
LEAGUE_AVG_SLG = 0.400
LEAGUE_AVG_ERA = 4.50
LEAGUE_AVG_FIP = 4.50

# ==============================================================================
# 工具函式
# ==============================================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

def get_safe_headers():
    """隨機產生一個模仿真實瀏覽器的 Header，規避 403/406 限制"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8,zh;q=0.7",
        "Origin": "https://mlb.com",
        "Referer": "https://mlb.com/"
    }

def random_delay(min_sec=1, max_sec=3):
    """加入隨機微幅延遲（Jitter），模擬人類點擊行為"""
    sleep_time = random.uniform(min_sec, max_sec)
    time.sleep(sleep_time)

def get_park_factor(venue_name):
    """取得場地因子"""
    for name, factor in PARK_FACTORS.items():
        if name.lower() in venue_name.lower():
            return factor
    return 1.00  # 預設聯盟平均

# ==============================================================================
# 天氣 API 整合
# ==============================================================================

def get_weather_data(city_name, state_code=None):
    """
    使用 OpenWeatherMap API 取得天氣數據
    
    Args:
        city_name: 城市名稱（例如：Los Angeles, New York）
        state_code: 州代碼（例如：CA, NY），可選
    
    Returns:
        dict: 天氣數據
            - temperature_f: 華氏溫度
            - wind_speed_mph: 風速 mph
            - wind_deg: 風向（度數）
            - humidity: 濕度 %
            - condition: 天氣狀況
    """
    # 如果 API Key 未設定，直接回傳預設值（不請求 API）
    if OPENWEATHER_API_KEY == 'YOUR_API_KEY_HERE':
        print("ℹ️ 天氣 API 未啟用，使用預設天氣數據（溫度 75°F, 風速 5mph）")
        return {
            "temperature_f": 75,
            "wind_speed_mph": 5,
            "wind_deg": 180,
            "humidity": 50,
            "condition": "Clear"
        }
    
    # 構建查詢參數
    if state_code:
        query = f"{city_name},{state_code},US"
    else:
        query = f"{city_name},US"
    
    params = {
        'q': query,
        'appid': OPENWEATHER_API_KEY,
        'units': 'imperial'  # 使用華氏溫度
    }
    
    try:
        response = requests.get(
            OW_BASE_URL,
            params=params,
            headers={'User-Agent': 'MLB-Predictor/1.0'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # 轉換數據
            temperature_f = data['main']['temp']
            wind_speed_mph = data['wind']['speed']
            wind_deg = data['wind'].get('deg', 180)
            humidity = data['main']['humidity']
            condition = data['weather'][0]['main']
            
            return {
                "temperature_f": round(temperature_f, 1),
                "wind_speed_mph": round(wind_speed_mph, 1),
                "wind_deg": wind_deg,
                "humidity": humidity,
                "condition": condition
            }
        elif response.status_code == 401:
            print("⚠️ 天氣 API 401 錯誤：API Key 無效或未生效")
            print("   請確認 API Key 已申請，且等待 10-60 分鐘生效")
            print("   暫時使用預設天氣數據繼續執行...")
            return {
                "temperature_f": 75,
                "wind_speed_mph": 5,
                "wind_deg": 180,
                "humidity": 50,
                "condition": "Clear"
            }
        else:
            print(f"⚠️ 天氣 API 請求失敗，狀態碼: {response.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ 天氣 API 請求異常: {e}")
        return None


def get_wind_direction(degrees):
    """
    將風向度數轉換為簡易方向
    
    Args:
        degrees: 風向度數（0-360）
    
    Returns:
        str: 風向描述
            - 'in': 向內吹（不利全壘打）
            - 'out': 向外吹（有利全壘打）
            - 'cross': 側風
            - 'none': 無風或直吹
    """
    if degrees is None or degrees == 0:
        return 'none'
    
    # 根據球場方向調整（簡化版）
    # 一般來說：
    # - 外野方向的風（例如：右外野 270°）
    # - 這裡使用簡化規則
    
    if degrees < 20 or degrees >= 340:
        return 'north'
    elif 20 <= degrees < 160:
        return 'east'
    elif 160 <= degrees < 200:
        return 'south'
    else:
        return 'west'


def calculate_weather_adjustment(temperature_f, wind_speed_mph, wind_deg, venue_name=""):
    """
    計算天氣調整係數
    
    Args:
        temperature_f: 華氏溫度
        wind_speed_mph: 風速 mph
        wind_deg: 風向度數
        venue_name: 球場名稱（用於判斷風向影響）
    
    Returns:
        float: 調整係數（1.0 = 無影響）
    """
    # 溫度調整：每升高 10°F，得分增加約 1%
    temp_adjust = 1.0 + (temperature_f - 70) * 0.002
    
    # 風向調整
    wind_adjust = 1.0
    wind_dir = get_wind_direction(wind_deg)
    
    # 根據球場特性調整風向影響
    venue_lower = venue_name.lower()
    
    if 'coors' in venue_lower:
        # 丹佛高海拔，風向影響較小
        if wind_dir in ['west', 'east']:
            wind_adjust = 1.0 + (wind_speed_mph * 0.005)
    elif 'yankee' in venue_lower or 'fenway' in venue_lower:
        # 美聯球場，右外野風向重要
        if wind_dir == 'west' and wind_speed_mph > 5:
            wind_adjust = 1.0 + (wind_speed_mph * 0.01)
        elif wind_dir == 'east' and wind_speed_mph > 10:
            wind_adjust = 1.0 - (wind_speed_mph * 0.005)
    else:
        # 通用規則
        if wind_dir in ['west', 'east'] and wind_speed_mph > 8:
            wind_adjust = 1.0 + (wind_speed_mph * 0.008)
        elif wind_dir in ['north', 'south'] and wind_speed_mph > 10:
            wind_adjust = 1.0 - (wind_speed_mph * 0.005)
    
    return round(temp_adjust * wind_adjust, 3)


# ==============================================================================
# Google Sheets 操作
# ==============================================================================

def upsert_to_google_sheet_hybrid(spreadsheet_id, sheet_name, df, id_column_name):
    """
    結合試算表 ID 與分頁名稱，以 'Upsert' 邏輯寫入 Google Sheet
    """
    if df is None or df.empty:
        print(f"⚠️ ({sheet_name}) 沒有新資料需要處理。")
        return
        
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            existing_data = worksheet.get_all_records()
            df_existing = pd.DataFrame(existing_data)
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="1000", cols="20")
            df_filled = df.fillna("")
            data_to_upload = [df_filled.columns.values.tolist()] + df_filled.values.tolist()
            worksheet.update(data_to_upload)
            print(f"✨ 發現全新分頁，已直接建立並寫入 {len(df)} 筆資料到 ({sheet_name})。")
            return

        if df_existing.empty or id_column_name not in df_existing.columns:
            df_filled = df.fillna("")
            if worksheet.row_count == 0 or not worksheet.row_values(1):
                data_to_upload = [df_filled.columns.values.tolist()] + df_filled.values.tolist()
                worksheet.update(data_to_upload)
            else:
                worksheet.append_rows(df_filled.values.tolist())
            print(f"📝 雲端表格為空，已直接寫入 {len(df)} 筆新資料到 ({sheet_name})。")
            return

        df[id_column_name] = df[id_column_name].astype(str)
        df_existing[id_column_name] = df_existing[id_column_name].astype(str)
        id_to_row_map = {str(id_val): index + 2 for index, id_val in enumerate(df_existing[id_column_name])}

        new_rows_to_append = []
        update_count = 0
        insert_count = 0
        df_filled_new = df.fillna("")

        for _, row in df_filled_new.iterrows():
            current_id = str(row[id_column_name])
            row_list = row.values.tolist()

            if current_id in id_to_row_map:
                target_row_number = id_to_row_map[current_id]
                end_column_letter = chr(64 + len(row_list))
                cell_range = f"A{target_row_number}:{end_column_letter}{target_row_number}"
                worksheet.update([row_list], cell_range)
                update_count += 1
            else:
                new_rows_to_append.append(row_list)
                insert_count += 1

        if new_rows_to_append:
            worksheet.append_rows(new_rows_to_append)

        print(f"📊 ({sheet_name}) 同步完成！共更新 {update_count} 筆現有資料，新增 {insert_count} 筆新資料。")

    except Exception as e:
        print(f"❌ 同步到 Google Sheet ({sheet_name}) 失敗: {e}")


# ==============================================================================
# MLB API 資料抓取
# ==============================================================================

def get_pitcher_stats(pitcher_id, season=2026):
    """
    取得投手賽季統計數據
    
    回傳欄位：
    - PitcherId, PitcherName, TeamId, TeamName, pitchHand
    - GamesStarted, GamesPlayed, InningsPitched
    - ERA, WHIP, K%, BB%, BABIP
    - TotalBattersFaced, K/9, BB/9
    """
    domain = "statsapi.mlb.com"
    path = f"/api/v1/people/{pitcher_id}/stats"
    url = f"https://{domain}{path}"
    
    params = {
        "stats": "seasonAdvanced",
        "group": "pitching",
        "season": season
    }
    
    try:
        random_delay(1.5, 3)
        adv_response = requests.get(url, params=params, headers=get_safe_headers(), timeout=10)
        random_delay(0.5, 1.5)
        params["stats"] = "statsSingleSeason"
        std_response = requests.get(url, params=params, headers=get_safe_headers(), timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"❌ 網路連線失敗: {e}")
        return None
        
    if adv_response.status_code != 200 or std_response.status_code != 200:
        print(f"❌ 無法取得投手數據。狀態碼: {adv_response.status_code}")
        return None
        
    try:
        adv_json = adv_response.json()
        std_json = std_response.json()
        
        if "stats" not in std_json or not std_json["stats"] or not std_json["stats"][0].get("splits"):
            print(f"⚠️ 找不到該投手在 {season} 賽季的數據")
            return None
            
        std_splits = std_json["stats"][0]["splits"][0]
        std_stats = std_splits.get("stat", {})
        player_info = std_splits.get("player", {})
        
        adv_stats = {}
        if "stats" in adv_json and adv_json["stats"] and adv_json["stats"][0].get("splits"):
            adv_stats = adv_json["stats"][0]["splits"][0].get("stat", {})
        
        # 處理投球慣用手
        pitch_hand = player_info.get("pitchHand", {}).get("code")
        if not pitch_hand:
            try:
                p_url = f"https://{domain}/api/v1/people/{pitcher_id}"
                p_res = requests.get(p_url, timeout=5).json()
                pitch_hand = p_res.get("people", [{}])[0].get("pitchHand", {}).get("code", "R")
            except:
                pitch_hand = "R"

        # 計算 K% 與 BB%
        bf = std_stats.get("battersFaced", 0)
        so = std_stats.get("strikeOuts", 0)
        bb = std_stats.get("baseOnBalls", 0)
        
        if bf > 0:
            k_rate = f"{(so / bf) * 100:.1f}%"
            bb_rate = f"{(bb / bf) * 100:.1f}%"
        else:
            k_rate = "0.0%"
            bb_rate = "0.0%"

        # 處理 BABIP
        babip_val = adv_stats.get("babip")
        if not babip_val:
            h = std_stats.get("hits", 0)
            hr = std_stats.get("homeRuns", 0)
            ab = std_stats.get("atBats", 0)
            sf = std_stats.get("sacFlies", 0)
            denom = (ab - so - hr + sf)
            babip_val = f"{(h - hr) / denom:.3f}" if denom > 0 else ".000"

        pitcher_dict = {
            "PitcherId": pitcher_id,
            "PitcherName": player_info.get("fullName", "Unknown Player"),
            "TeamId": std_splits.get("team", {}).get("id"),
            "TeamName": std_splits.get("team", {}).get("name"),
            "pitchHand": pitch_hand,
            "GamesStarted": std_stats.get("gamesStarted"),
            "GamesPlayed": std_stats.get("gamesPlayed"),
            "InningsPitched": std_stats.get("inningsPitched"),
            "TotalBattersFaced": bf,
            "K%": k_rate,
            "BB%": bb_rate,
            "WHIP": std_stats.get("whip"),
            "ERA": std_stats.get("era"),
            "BABIP": babip_val,
            "StrikeoutsPer9Inn": std_stats.get("strikeoutsPer9Inn"),
            "WalksPer9Inn": std_stats.get("walksPer9Inn"),
            "K-BB%": f"{float(k_rate.rstrip('%')) - float(bb_rate.rstrip('%')):.1f}%" if bf > 0 else "0.0%",
        }
        return pd.DataFrame([pitcher_dict])
    except Exception as e:
        print(f"⚠️ 投手數據欄位解析失敗: {e}")
        return None


def get_games_by_date(game_date):
    """
    取得當天所有 MLB 比賽數據
    
    包含：
    - 基本賽程資訊
    - 先發投手數據
    - 球隊當場打擊數據（AVG, OBP, SLG, OPS, HR, R, RBI）
    - 球隊當場投球數據
    - 牛棚投手 ID 列表
    - 場地因子
    - 天氣數據
    """
    domain = "statsapi.mlb.com"
    
    # 步驟 1：取得基本賽程
    schedule_url = f"https://{domain}/api/v1/schedule"
    schedule_params = {
        "sportId": 1,
        "date": game_date
    }
    
    try:
        response = requests.get(schedule_url, params=schedule_params, headers=get_safe_headers(), timeout=12)
        if response.status_code != 200:
            print(f"❌ 賽程基本 API 請求失敗，狀態碼: {response.status_code}")
            return None
        schedule_data = response.json()
    except Exception as e:
        print(f"❌ 抓取基本賽程時發生異常: {e}")
        return None
        
    dates = schedule_data.get("dates", [])
    if not dates:
        return pd.DataFrame()
        
    games_list = []
    base_games = dates[0].get("games", [])
    print(f" [Docker 備援防禦啟動] 成功獲取基本賽程，開始穿透 {len(base_games)} 場比賽的 Boxscore & Linescore 數據...")
    
    # 步驟 2：疊代每場比賽
    for idx, base_game in enumerate(base_games):
        game_id = base_game.get("gamePk")
        teams = base_game.get("teams", {})
        away_team = teams.get("away", {})
        home_team = teams.get("home", {})
        venue_name = base_game.get("venue", {}).get("name", "")
        
        # 預設變數
        away_pitcher_name, away_pitcher_id = "TBD", 0
        home_pitcher_name, home_pitcher_id = "TBD", 0
        current_inning = 0
        inning_state = "Scheduled"
        
        away_pitcher_ip = "0.0"
        away_pitcher_h = away_pitcher_er = away_pitcher_k = away_pitcher_bb = 0
        home_pitcher_ip = "0.0"
        home_pitcher_h = home_pitcher_er = home_pitcher_k = home_pitcher_bb = 0
        
        # 牛棚投手 ID 列表
        away_bullpen_ids = []
        home_bullpen_ids = []
        
        # 球隊打擊數據
        away_batting = {}
        home_batting = {}
        
        # 球隊投球數據
        away_pitching = {}
        home_pitching = {}
        
        # 天氣數據
        weather_data = None
        
        random_delay(0.2, 0.5)
        
        # 子步驟 A：呼叫單場 boxscore
        boxscore_url = f"https://{domain}/api/v1/game/{game_id}/boxscore"
        try:
            box_res = requests.get(boxscore_url, headers=get_safe_headers(), timeout=10)
            if box_res.status_code == 200:
                box_data = box_res.json()
                box_teams = box_data.get("teams", {})
                
                # --- 穿透客隊先發與數據 ---
                away_box = box_teams.get("away", {})
                away_pitchers_list = away_box.get("pitchers", [])
                if away_pitchers_list:
                    first_away_pitcher_id = away_pitchers_list[0]
                    away_pitcher_id = first_away_pitcher_id
                    
                    player_node = away_box.get("players", {}).get(f"ID{first_away_pitcher_id}", {})
                    away_pitcher_name = player_node.get("person", {}).get("fullName", "TBD")
                    
                    pitching_stats = player_node.get("stats", {}).get("pitching", {})
                    if pitching_stats:
                        away_pitcher_ip = pitching_stats.get("inningsPitched", "0.0")
                        away_pitcher_h = int(pitching_stats.get("hits", 0))
                        away_pitcher_er = int(pitching_stats.get("earnedRuns", 0))
                        away_pitcher_k = int(pitching_stats.get("strikeOuts", 0))
                        away_pitcher_bb = int(pitching_stats.get("baseOnBalls", 0))
                
                # --- 穿透主隊先發與數據 ---
                home_box = box_teams.get("home", {})
                home_pitchers_list = home_box.get("pitchers", [])
                if home_pitchers_list:
                    first_home_pitcher_id = home_pitchers_list[0]
                    home_pitcher_id = first_home_pitcher_id
                    
                    player_node = home_box.get("players", {}).get(f"ID{first_home_pitcher_id}", {})
                    home_pitcher_name = player_node.get("person", {}).get("fullName", "TBD")
                    
                    pitching_stats = player_node.get("stats", {}).get("pitching", {})
                    if pitching_stats:
                        home_pitcher_ip = pitching_stats.get("inningsPitched", "0.0")
                        home_pitcher_h = int(pitching_stats.get("hits", 0))
                        home_pitcher_er = int(pitching_stats.get("earnedRuns", 0))
                        home_pitcher_k = int(pitching_stats.get("strikeOuts", 0))
                        home_pitcher_bb = int(pitching_stats.get("baseOnBalls", 0))
                
                # --- 取得牛棚投手 ID ---
                away_bullpen_ids = away_box.get("bullpen", [])
                home_bullpen_ids = home_box.get("bullpen", [])
                
                # --- 取得球隊打擊數據 ---
                away_batting = away_box.get("teamStats", {}).get("batting", {})
                home_batting = home_box.get("teamStats", {}).get("batting", {})
                
                # --- 取得球隊投球數據 ---
                away_pitching = away_box.get("teamStats", {}).get("pitching", {})
                home_pitching = home_box.get("teamStats", {}).get("pitching", {})
                
        except Exception as e:
            pass

        # 子步驟 B：呼叫單場 linescore
        linescore_url = f"https://{domain}/api/v1/game/{game_id}/linescore"
        try:
            line_res = requests.get(linescore_url, headers=get_safe_headers(), timeout=10)
            if line_res.status_code == 200:
                line_data = line_res.json()
                current_inning = line_data.get("currentInning", 0)
                
                state = line_data.get("inningState")
                ordinal = line_data.get("currentInningOrdinal")
                
                if state and ordinal:
                    inning_state = f"{state} {ordinal}"
                elif base_game.get("status", {}).get("abstractGameState") == "Final":
                    inning_state = "Final"
        except Exception as e:
            pass
        
        # 子步驟 C：取得天氣數據
        try:
            # 從賽程資料中提取城市名稱
            away_city = away_team.get("team", {}).get("locationName", "")
            home_city = home_team.get("team", {}).get("locationName", "")
            
            # 使用主隊城市查詢天氣
            weather_data = get_weather_data(home_city)
        except Exception as e:
            print(f"⚠️ 天氣數據抓取失敗: {e}")
            weather_data = None

        # 計算天氣調整係數
        weather_adjustment = 1.0
        if weather_data:
            weather_adjustment = calculate_weather_adjustment(
                weather_data['temperature_f'],
                weather_data['wind_speed_mph'],
                weather_data['wind_deg'],
                venue_name
            )
        
        # 組合出包含完整數據的資料列
        games_list.append({
            "Game_Date": game_date,
            "Game_ID": game_id,
            "Away_Team_Name": away_team.get("team", {}).get("name"),
            "Home_Team_Name": home_team.get("team", {}).get("name"),
            "Away_Started_Pitcher_Name": away_pitcher_name,
            "Away_Started_Pitcher_ID": int(away_pitcher_id),
            "Home_Started_Pitcher_Name": home_pitcher_name,
            "Home_Started_Pitcher_ID": int(home_pitcher_id),
            
            # 先發投手當場投球數據
            "Away_Pitcher_IP": away_pitcher_ip,
            "Away_Pitcher_H": away_pitcher_h,
            "Away_Pitcher_ER": away_pitcher_er,
            "Away_Pitcher_K": away_pitcher_k,
            "Away_Pitcher_BB": away_pitcher_bb,
            "Home_Pitcher_IP": home_pitcher_ip,
            "Home_Pitcher_H": home_pitcher_h,
            "Home_Pitcher_ER": home_pitcher_er,
            "Home_Pitcher_K": home_pitcher_k,
            "Home_Pitcher_BB": home_pitcher_bb,
            
            # 比分
            "Away_Score": away_team.get("score", 0),
            "Home_Score": home_team.get("score", 0),
            "Game_State": base_game.get("status", {}).get("detailedState"),
            "Current_Inning": int(current_inning),
            "Inning_State": inning_state,
            "Venue_Name": venue_name,
            "Start_Time_UTC": base_game.get("gameDate"),
            
            # 場地因子
            "Park_Factor": get_park_factor(venue_name),
            
            # 天氣數據
            "Weather_Temperature_F": weather_data['temperature_f'] if weather_data else "N/A",
            "Weather_Wind_Speed_MPH": weather_data['wind_speed_mph'] if weather_data else "N/A",
            "Weather_Wind_Deg": weather_data['wind_deg'] if weather_data else "N/A",
            "Weather_Humidity": weather_data['humidity'] if weather_data else "N/A",
            "Weather_Condition": weather_data['condition'] if weather_data else "N/A",
            "Weather_Adjustment": round(weather_adjustment, 3),
            
            # 客隊當場打擊數據
            "Away_Batting_AVG": away_batting.get("avg"),
            "Away_Batting_OBP": away_batting.get("obp"),
            "Away_Batting_SLG": away_batting.get("slg"),
            "Away_Batting_OPS": away_batting.get("ops"),
            "Away_Batting_HR": away_batting.get("homeRuns"),
            "Away_Batting_R": away_batting.get("runs"),
            "Away_Batting_RBI": away_batting.get("rbi"),
            "Away_Batting_Hits": away_batting.get("hits"),
            "Away_Batting_BB": away_batting.get("baseOnBalls"),
            "Away_Batting_SO": away_batting.get("strikeOuts"),
            "Away_Batting_PA": away_batting.get("plateAppearances"),
            
            # 主隊當場打擊數據
            "Home_Batting_AVG": home_batting.get("avg"),
            "Home_Batting_OBP": home_batting.get("obp"),
            "Home_Batting_SLG": home_batting.get("slg"),
            "Home_Batting_OPS": home_batting.get("ops"),
            "Home_Batting_HR": home_batting.get("homeRuns"),
            "Home_Batting_R": home_batting.get("runs"),
            "Home_Batting_RBI": home_batting.get("rbi"),
            "Home_Batting_Hits": home_batting.get("hits"),
            "Home_Batting_BB": home_batting.get("baseOnBalls"),
            "Home_Batting_SO": home_batting.get("strikeOuts"),
            "Home_Batting_PA": home_batting.get("plateAppearances"),
            
            # 客隊當場投球數據
            "Away_Pitching_Era": away_pitching.get("era"),
            "Away_Pitching_WHIP": away_pitching.get("whip"),
            "Away_Pitching_Hits": away_pitching.get("hits"),
            "Away_Pitching_ER": away_pitching.get("earnedRuns"),
            "Away_Pitching_BB": away_pitching.get("baseOnBalls"),
            "Away_Pitching_SO": away_pitching.get("strikeOuts"),
            "Away_Pitching_IP": away_pitching.get("inningsPitched"),
            
            # 主隊當場投球數據
            "Home_Pitching_Era": home_pitching.get("era"),
            "Home_Pitching_WHIP": home_pitching.get("whip"),
            "Home_Pitching_Hits": home_pitching.get("hits"),
            "Home_Pitching_ER": home_pitching.get("earnedRuns"),
            "Home_Pitching_BB": home_pitching.get("baseOnBalls"),
            "Home_Pitching_SO": home_pitching.get("strikeOuts"),
            "Home_Pitching_IP": home_pitching.get("inningsPitched"),
            
            # 牛棚投手 ID（用於後續抓取賽季數據）
            "Away_Bullpen_IDS": "|".join(map(str, away_bullpen_ids)),
            "Home_Bullpen_IDS": "|".join(map(str, home_bullpen_ids)),
        })
        
    return pd.DataFrame(games_list)


def get_bullpen_season_stats(bullpen_ids, season=2026):
    """
    對牛棚投手列表，逐一抓取賽季數據
    
    回傳欄位：
    - PitcherId, PitcherName, TeamId, TeamName
    - GamesPlayed (GP), GamesFinished (GF)
    - Saves (SV), Holds (HLD), BlownSaves (BS)
    - InningsPitched (IP), ERA, WHIP
    - K%, BB%, K-BB%
    - StrikeoutsPer9Inn, WalksPer9Inn
    """
    if not bullpen_ids:
        return pd.DataFrame()
    
    # 批次處理：每批 20 人，批次間隔 10 秒
    BATCH_SIZE = 20
    DELAY_BETWEEN_BATCHES = 10
    
    bullpen_list = []
    total_count = len(bullpen_ids)
    total_batches = (total_count + BATCH_SIZE - 1) // BATCH_SIZE
    
    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, total_count)
        batch = bullpen_ids[start:end]
        
        print(f"   📦 批次 {batch_idx + 1}/{total_batches}：處理 {len(batch)} 位投手")
        
        batch_results = []
        for pid in batch:
            p_stats = None
            max_retries = 2
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        wait_time = random.uniform(3.0, 6.0)
                        print(f"      ⚠️ 重試中，等待 {wait_time:.1f} 秒...")
                        time.sleep(wait_time)
                    
                    p_stats = get_pitcher_stats(pid, season=season)
                    break
                except Exception as retry_err:
                    p_stats = None
                    if attempt == max_retries - 1:
                        print(f"      ❌ 嘗試 {max_retries}次 後仍連線失敗，跳過投手 {pid}")
            
            if p_stats is not None and isinstance(p_stats, pd.DataFrame) and not p_stats.empty:
                batch_results.append(p_stats)
        
        bullpen_list.extend(batch_results)
        
        # 批次間歇（避免被 406 擋掉）
        if batch_idx < total_batches - 1:
            delay = DELAY_BETWEEN_BATCHES + random.uniform(0, 5)
            print(f"   ⏳ 等待 {delay:.1f} 秒...")
            time.sleep(delay)
    
    if bullpen_list:
        return pd.concat(bullpen_list, ignore_index=True)
    return pd.DataFrame()


# ==============================================================================
# 主要執行流程
# ==============================================================================

if __name__ == "__main__":
    # 請在此處填入您 Google Sheet 的長串 Spreadsheet ID
    TARGET_SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE"  # 替換為實際 ID
    
    print("🎬 === 開始執行 MLB 每日數據自動化同步流水線（大小分預測完整版 v2.0）===")
    
    # 取得日期參數
    has_date_arg = len(sys.argv) > 1
    if has_date_arg:
        us_today_date = sys.argv[1]
        try:
            current_season = int(us_today_date.split("-")[0])
            print(f"📅 命令列參數偵測成功！指定日期: {us_today_date}")
            print(f"   → 只抓取該日期比賽數據，不抓取投手賽季數據")
        except Exception:
            print("❌ 輸入的日期格式有誤，請確保格式為 YYYY-MM-DD (例如: 2024-04-15)")
            sys.exit(1)
    else:
        tz_us_eastern = pytz.timezone("US/Eastern")
        current_us_time = datetime.datetime.now(tz_us_eastern)
        us_today_date = current_us_time.strftime("%Y-%m-%d")
        current_season = current_us_time.year
        print(f"📅 未偵測到日期參數，自動啟用今日即時同步機制。")
    
    print(f"📅 鎖定查詢之美國日期為: {us_today_date}，目標賽季: {current_season}")
    
    # 計算明天日期
    today_dt = datetime.datetime.strptime(us_today_date, "%Y-%m-%d")
    tomorrow_dt = today_dt + datetime.timedelta(days=1)
    tomorrow_date = tomorrow_dt.strftime("%Y-%m-%d")
    
    # ==============================================================================
    # 步驟 1：抓取比賽數據
    # ==============================================================================
    if has_date_arg:
        # 模式 A：只抓取指定日期的比賽（不抓投手數據）
        print(f"\n📡 正在從 MLB 官方伺服器抓取 {us_today_date} 的比賽數據...")
        df_games = get_games_by_date(us_today_date)
        
        if df_games is None or df_games.empty:
            print(f"📅 日期 {us_today_date} 當天大聯盟沒有安排常規賽事。主流程提前結束。")
            sys.exit(0)
        else:
            print(f"✅ 成功獲取 {us_today_date} 比賽資料，當日共計 {len(df_games)} 場對決。")
            print(f"ℹ️ 指定日期模式：只抓取比賽數據，不抓取投手賽季數據。")
    else:
        # 模式 B：抓取今天 + 明天比賽，並抓取投手賽季數據
        print(f"\n📡 正在從 MLB 官方伺服器抓取 {us_today_date} 和 {tomorrow_date} 的比賽數據...")
        df_today = get_games_by_date(us_today_date)
        df_tomorrow = get_games_by_date(tomorrow_date)
        
        # 合併今天和明天的數據
        if df_today is not None and not df_today.empty:
            print(f"✅ 成功獲取 {us_today_date} 比賽資料，當日共計 {len(df_today)} 場對決。")
        else:
            df_today = pd.DataFrame()
            print(f"⚠️ {us_today_date} 當天大聯盟沒有安排常規賽事。")
        
        if df_tomorrow is not None and not df_tomorrow.empty:
            print(f"✅ 成功獲取 {tomorrow_date} 比賽資料，當日共計 {len(df_tomorrow)} 場對決。")
        else:
            df_tomorrow = pd.DataFrame()
            print(f"⚠️ {tomorrow_date} 當天大聯盟沒有安排常規賽事。")
        
        # 合併今天和明天的數據
        df_games = pd.concat([df_today, df_tomorrow], ignore_index=True) if not df_today.empty or not df_tomorrow.empty else pd.DataFrame()
        
        if df_games.empty:
            print(f"📅 今天和明天都沒有安排常規賽事。主流程提前結束。")
            sys.exit(0)
        else:
            print(f"📊 今天和明天共計 {len(df_games)} 場對決（今天 {len(df_today)} 場，明天 {len(df_tomorrow)} 場）。")
            print(f"ℹ️ 自動模式：將抓取今天比賽的先發投手與牛棚投手賽季數據。")
    
    # ==============================================================================
    # 步驟 2：只在不帶日期參數時才抓取投手數據
    # ==============================================================================
    if has_date_arg:
        # 指定日期模式：跳過投手數據抓取
        print(f"\n⏭️ 跳過投手數據抓取（指定日期模式）")
        df_pitchers = pd.DataFrame()
        df_bullpen = pd.DataFrame()
    else:
        # 自動模式：抓取先發投手和牛棚投手賽季數據
        
        # 只抓取「今天」的先發投手（不抓明天的）
        df_today_games = df_games[df_games["Game_Date"] == us_today_date] if not df_games.empty else pd.DataFrame()
        
        if df_today_games.empty:
            print(f"\n⚠️ 今天沒有比賽，跳過投手數據抓取。")
            df_pitchers = pd.DataFrame()
            df_bullpen = pd.DataFrame()
        else:
            # 步驟 2：收集今天比賽的先發投手 ID
            pitcher_ids_set = set()
            for _, row in df_today_games.iterrows():
                away_pid = row["Away_Started_Pitcher_ID"]
                home_pid = row["Home_Started_Pitcher_ID"]
                if away_pid and int(away_pid) != 0:
                    pitcher_ids_set.add(int(away_pid))
                if home_pid and int(home_pid) != 0:
                    pitcher_ids_set.add(int(home_pid))
            
            print(f"\n🎯 經交叉比對，今日共需抓取 {len(pitcher_ids_set)} 位先發投手的賽季數據...")
            
            # 步驟 3：抓取先發投手賽季數據
            pitchers_data_list = []
            processed_count = 0
            
            for p_id in pitcher_ids_set:
                processed_count += 1
                print(f"   [進度 {processed_count}/{len(pitcher_ids_set)}] 正在獲取先發投手 ID: {p_id} 的賽季統計...")
                
                p_stats = None
                max_retries = 3
                
                for attempt in range(max_retries):
                    try:
                        if attempt > 0:
                            wait_time = random.uniform(5.0, 10.0)
                            print(f"      ⚠️ 偵測到大聯盟限速或卡頓，啟動第 {attempt + 1} 次全面重試，後台避風頭 {wait_time:.1f} 秒...")
                            time.sleep(wait_time)
                        
                        p_stats = get_pitcher_stats(p_id, season=current_season)
                        break
                    except Exception as retry_err:
                        p_stats = None
                        if attempt == max_retries - 1:
                            print(f"      ❌ 嘗試 {max_retries}次 後仍連線失敗，原因: {retry_err}")
                
                if p_stats is not None and isinstance(p_stats, pd.DataFrame) and not p_stats.empty:
                    pitchers_data_list.append(p_stats)
                else:
                    print(f"      ⚠️ 投手 ID {p_id} 最終無法取得有效數據，跳過此球員。")
            
            if pitchers_data_list:
                df_pitchers = pd.concat(pitchers_data_list, ignore_index=True)
            else:
                df_pitchers = pd.DataFrame()
            
            # 步驟 4：只抓取「今天有出賽」的牛棚投手
            print("\n🎯 篩選今天有出賽的牛棚投手...")
            active_bullpen_ids = []
            games_processed = 0
            
            for _, row in df_today_games.iterrows():
                game_id = row["Game_ID"]
                games_processed += 1
                
                # 從 boxscore 中提取今天有投球的牛棚投手
                box_url = f"https://{MLB_BASE_URL}/game/{game_id}/boxscore"
                try:
                    box_res = requests.get(box_url, headers=get_safe_headers(), timeout=10)
                    if box_res.status_code == 200:
                        box_data = box_res.json()
                        teams = box_data.get("teams", {})
                        
                        for side in ["away", "home"]:
                            team_box = teams.get(side, {})
                            players = team_box.get("players", {})
                            
                            # 檢查所有投手（包含先發和牛棚）
                            for player_key, player_data in players.items():
                                stats = player_data.get("stats", {}).get("pitching", {})
                                
                                # 如果有投球局數 > 0，表示今天有上場
                                ip = stats.get("inningsPitched", "0")
                                if ip and float(ip) > 0:
                                    # 提取投手 ID（從 player_key 如 "ID123456" 轉成 123456）
                                    if player_key.startswith("ID"):
                                        pid = int(player_key[2:])
                                        active_bullpen_ids.append(pid)
                except Exception as e:
                    print(f"  ⚠️ 遊戲 {game_id} boxscore 抓取失敗: {e}")
                    continue
            
            # 去重
            active_bullpen_ids = list(set(active_bullpen_ids))
            print(f"✅ 從 {games_processed} 場比賽中篩選出 {len(active_bullpen_ids)} 位今天有出賽的牛棚投手")
            
            # 步驟 5：抓取牛棚投手賽季數據
            if active_bullpen_ids:
                print("📡 正在抓取牛棚投手賽季數據...")
                df_bullpen = get_bullpen_season_stats(active_bullpen_ids, season=current_season)
            else:
                df_bullpen = pd.DataFrame()
                print("ℹ️ 當日無牛棚投手出賽數據。")
        p_stats = None
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = random.uniform(5.0, 10.0)
                    print(f"      ⚠️ 偵測到大聯盟限速或卡頓，啟動第 {attempt + 1} 次全面重試，後台避風頭 {wait_time:.1f} 秒...")
                    time.sleep(wait_time)
                
                p_stats = get_pitcher_stats(p_id, season=current_season)
                break
            except Exception as retry_err:
                p_stats = None
                if attempt == max_retries - 1:
                    print(f"      ❌ 嘗試 {max_retries}次 後仍連線失敗，原因: {retry_err}")
        
        if p_stats is not None and isinstance(p_stats, pd.DataFrame) and not p_stats.empty:
            pitchers_data_list.append(p_stats)
        else:
            print(f"      ⚠️ 投手 ID {p_id} 最終無法取得有效數據，跳過此球員。")
    
    if pitchers_data_list:
        df_pitchers = pd.concat(pitchers_data_list, ignore_index=True)
    else:
        df_pitchers = pd.DataFrame()
    
    # 步驟 4：只抓取「今天有出賽」的牛棚投手（避免 406 封鎖）
    print("\n🎯 篩選今天有出賽的牛棚投手...")
    active_bullpen_ids = []
    games_processed = 0
    
    for _, row in df_games.iterrows():
        game_id = row["Game_ID"]
        games_processed += 1
        
        # 從 boxscore 中提取今天有投球的牛棚投手
        box_url = f"https://{MLB_BASE_URL}/game/{game_id}/boxscore"
        try:
            box_res = requests.get(box_url, headers=get_safe_headers(), timeout=10)
            if box_res.status_code == 200:
                box_data = box_res.json()
                teams = box_data.get("teams", {})
                
                for side in ["away", "home"]:
                    team_box = teams.get(side, {})
                    players = team_box.get("players", {})
                    
                    # 檢查所有投手（包含先發和牛棚）
                    for player_key, player_data in players.items():
                        stats = player_data.get("stats", {}).get("pitching", {})
                        
                        # 如果有投球局數 > 0，表示今天有上場
                        ip = stats.get("inningsPitched", "0")
                        if ip and float(ip) > 0:
                            # 提取投手 ID（從 player_key 如 "ID123456" 轉成 123456）
                            if player_key.startswith("ID"):
                                pid = int(player_key[2:])
                                active_bullpen_ids.append(pid)
        except Exception as e:
            print(f"  ⚠️ 遊戲 {game_id} boxscore 抓取失敗: {e}")
            continue
    
    # 去重
    active_bullpen_ids = list(set(active_bullpen_ids))
    print(f"✅ 從 {games_processed} 場比賽中篩選出 {len(active_bullpen_ids)} 位今天有出賽的牛棚投手")
    
    # 步驟 5：抓取牛棚投手賽季數據
    if active_bullpen_ids:
        print("📡 正在抓取牛棚投手賽季數據...")
        df_bullpen = get_bullpen_season_stats(active_bullpen_ids, season=current_season)
    else:
        df_bullpen = pd.DataFrame()
        print("ℹ️ 當日無牛棚投手出賽數據。")
    
    # 步驟 6：寫入 Google Sheets
    print("\n☁️ 正在連線至 Google Sheets 進行智慧同步 (Upsert)...")
    
    # 寫入比賽數據表
    upsert_to_google_sheet_hybrid(
        spreadsheet_id=TARGET_SPREADSHEET_ID,
        sheet_name="team_stats",
        df=df_games,
        id_column_name="Game_ID"
    )
    
    # 寫入先發投手數據表
    if not df_pitchers.empty:
        upsert_to_google_sheet_hybrid(
            spreadsheet_id=TARGET_SPREADSHEET_ID,
            sheet_name="starting_pitchers",
            df=df_pitchers,
            id_column_name="PitcherId"
        )
    
    # 寫入牛棚投手數據表
    if not df_bullpen.empty:
        upsert_to_google_sheet_hybrid(
            spreadsheet_id=TARGET_SPREADSHEET_ID,
            sheet_name="bullpen_record",
            df=df_bullpen,
            id_column_name="PitcherId"
        )
    
    print("\n🏁 === MLB 每日數據自動化同步流水線 順利執行完畢 ===")
    print("\n📊 資料表結構說明：")
    print("  - team_stats: 比賽基本數據 + 先發投手 + 球隊當場打擊/投球 + 場地因子 + 天氣數據")
    print("    • 自動模式：包含今天和明天的比賽")
    print("    • 指定日期模式：只包含指定日期的比賽")
    print("    • Game_Date 欄位區分日期（YYYY-MM-DD）")
    print("  - starting_pitchers: 先發投手整季數據（ERA, WHIP, K%, BB%, BABIP, K-BB%）")
    print("    • 自動模式：只抓取今天比賽的先發投手")
    print("    • 指定日期模式：不抓取")
    print("  - bullpen_record: 牛棚投手整季數據（SV, HLD, ERA, WHIP, K-BB%）")
    print("    • 自動模式：只抓取今天有出賽的牛棚投手")
    print("    • 指定日期模式：不抓取")
    print("\n💡 預測模型使用建議：")
    print("  1. 從 team_stats 取得場地因子與天氣調整係數")
    print("  2. 從 team_stats 取得球隊當場打擊數據（OBP, SLG, OPS）")
    print("  3. 從 starting_pitchers 取得先發投手 ERA/WHIP/K-BB%")
    print("  4. 從 bullpen_record 取得牛棚整體實力（用於調整 λ）")
    print("  5. 使用 λ = 基礎 × 攻擊調整 × 投手調整 × 場地因子 × 天氣調整 計算預期得分")
    print("\n🌤️ 天氣數據欄位：")
    print("  - Weather_Temperature_F: 華氏溫度")
    print("  - Weather_Wind_Speed_MPH: 風速")
    print("  - Weather_Wind_Deg: 風向度數")
    print("  - Weather_Adjustment: 天氣調整係數（預設 1.0）")
    
    if has_date_arg:
        print(f"\n📅 執行模式：指定日期模式")
        print(f"  - 日期: {us_today_date}")
        print(f"  - 只抓取比賽數據，不抓取投手賽季數據")
    else:
        print(f"\n📅 執行模式：自動模式")
        print(f"  - 今天: {us_today_date}")
        print(f"  - 明天: {tomorrow_date}")
        print(f"  - 抓取今天比賽的先發投手與牛棚投手整季數據")
