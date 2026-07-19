#!/usr/bin/env python3
# /// script
# dependencies = [
#     "requests",
#     "beautifulsoup4",
#     "pandas",
#     "pytz"
# ]
# ///

"""
台灣運彩 MLB 大小分賠率爬蟲

功能：
1. 抓取 Odd168 或運彩官網的 MLB 大小分賠率
2. 儲存為 CSV 檔案
3. 可選擇上傳到 GitHub Pages 供網頁查看

使用方式：
    python scrape_odd168.py 2026-07-19
    python scrape_odd168.py  # 預設今天
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import os
import sys
import time
import random
from datetime import datetime, timedelta
import pytz

# ==============================================================================
# 配置
# ==============================================================================

# 目標日期（預設今天）
if len(sys.argv) > 1:
    target_date = sys.argv[1]
else:
    tz_us_eastern = pytz.timezone("US/Eastern")
    target_date = datetime.now(tz_us_eastern).strftime("%Y-%m-%d")

print(f"📅 目標日期: {target_date}")

# 爬蟲配置
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
}

# 嘗試多個來源
ODDS_SOURCES = [
    {
        'name': 'Odd168',
        'url_template': 'https://www.odd168.com/baseball/mlb/{date}',
        'parser': 'odd168_parser'
    },
    {
        'name': '運彩官網',
        'url_template': 'https://www.168.com.tw/sports/odds/mlb/{date}',
        'parser': 'odd168_parser'  # 共用解析器
    }
]

# 輸出目錄
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'odds_data')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==============================================================================
# 爬蟲函式
# ==============================================================================

def fetch_page(url, max_retries=3):
    """
    抓取網頁內容，帶有重試機制
    """
    for attempt in range(max_retries):
        try:
            print(f"   📡 嘗試連線: {url}")
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=15,
                verify=True
            )
            
            if response.status_code == 200:
                print(f"   ✅ 成功取得網頁")
                return response.text
            elif response.status_code == 403:
                print(f"   ⚠️ 403 Forbidden，等待後重試...")
                time.sleep(random.uniform(5, 10))
            elif response.status_code == 429:
                print(f"   ⚠️ 429 Too Many Requests，等待較長時間...")
                time.sleep(random.uniform(15, 30))
            else:
                print(f"   ⚠️ HTTP {response.status_code}，等待後重試...")
                time.sleep(random.uniform(3, 6))
                
        except requests.exceptions.Timeout:
            print(f"   ⚠️ 連線超時，重試中...")
            time.sleep(random.uniform(2, 5))
        except requests.exceptions.ConnectionError:
            print(f"   ⚠️ 連線失敗，重試中...")
            time.sleep(random.uniform(2, 5))
        except Exception as e:
            print(f"   ❌ 發生錯誤: {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(3, 7))
    
    return None

def odd168_parser(html_content):
    """
    解析 Odd168 網頁結構
    
    注意：實際的 HTML 結構需要根據網頁真實內容調整
    這裡提供通用解析邏輯
    """
    if not html_content:
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    games = []
    
    # 方法 1: 嘗試查找遊戲容器
    # 根據實際網頁結構調整選擇器
    game_containers = soup.find_all(['div', 'tr'], class_=lambda x: x and ('game' in x.lower() or 'match' in x.lower() or 'odds' in x.lower()))
    
    if not game_containers:
        # 方法 2: 查找所有包含賠率的元素
        game_containers = soup.find_all(['div', 'tr'])
    
    print(f"   🔍 找到 {len(game_containers)} 個潛在遊戲容器")
    
    for container in game_containers:
        try:
            # 提取球隊名稱
            teams_elem = container.find(['h2', 'h3', 'div', 'span'], 
                                      class_=lambda x: x and ('team' in x.lower() or 'vs' in x.lower()))
            if not teams_elem:
                teams_elem = container.find(['div', 'span'], string=lambda text: text and ('vs' in text.lower() or '@' in text))
            
            if teams_elem:
                teams_text = teams_elem.get_text(strip=True)
            else:
                teams_text = container.find(string=lambda text: text and ('vs' in text.lower() or '@' in text))
                teams_text = teams_text.strip() if teams_text else ""
            
            if not teams_text or len(teams_text) < 5:
                continue
            
            # 提取賠率數據
            odds_elements = container.find_all(['div', 'span', 'td'], 
                                             class_=lambda x: x and ('odd' in x.lower() or 'line' in x.lower() or 'price' in x.lower()))
            
            if not odds_elements:
                odds_elements = container.find_all(['div', 'span', 'td'])
            
            # 嘗試提取數字形式的賠率
            over_line = None
            under_line = None
            over_odds = None
            under_odds = None
            
            for elem in odds_elements:
                text = elem.get_text(strip=True)
                try:
                    # 嘗試解析為數字
                    if '.' in text:
                        num = float(text)
                        if 1.0 <= num <= 3.0:  # 合理的賠率範圍
                            if over_odds is None:
                                over_odds = num
                            elif under_odds is None:
                                under_odds = num
                except ValueError:
                    pass
            
            # 如果找到賠率，嘗試找到對應的門檻
            if over_odds and under_odds:
                # 查找總分門檻（通常在賠率附近）
                line_elements = container.find_all(['div', 'span', 'td'], 
                                                  string=lambda text: text and any(char.isdigit() for char in text))
                
                for elem in line_elements:
                    text = elem.get_text(strip=True)
                    try:
                        # 嘗試解析為總分門檻（如 8.5, 9.0）
                        if '.' in text:
                            num = float(text)
                            if 5.0 <= num <= 20.0:  # 合理的總分範圍
                                if over_line is None:
                                    over_line = num
                                elif under_line is None:
                                    under_line = num
                    except ValueError:
                        pass
                
                # 如果沒有找到門檻，使用預設值
                if not over_line:
                    over_line = 8.5
                if not under_line:
                    under_line = over_line
                
                games.append({
                    'teams': teams_text,
                    'over_line': over_line,
                    'under_line': under_line,
                    'over_odds': over_odds,
                    'under_odds': under_odds,
                    'source': 'Odd168'
                })
        
        except Exception as e:
            print(f"   ⚠️ 解析遊戲容器時發生錯誤: {e}")
            continue
    
    print(f"   ✅ 成功解析 {len(games)} 場比賽")
    return games

def parse_manual_input():
    """
    如果自動爬蟲失敗，提供手動輸入介面
    """
    print("\n" + "="*60)
    print("⚠️ 自動爬蟲無法取得數據")
    print("="*60)
    print("\n請手動輸入今日 MLB 比賽賠率：")
    print("格式：球隊 vs 球隊, Over門檻, Under門檻, Over賠率, Under賠率")
    print("範例：光芒 @ 紅襪, 8.5, 8.5, 1.85, 1.85")
    print("輸入 'done' 完成輸入\n")
    
    games = []
    
    while True:
        try:
            user_input = input("請輸入比賽數據: ").strip()
            
            if user_input.lower() == 'done':
                break
            
            if not user_input:
                continue
            
            parts = [p.strip() for p in user_input.split(',')]
            
            if len(parts) != 5:
                print("❌ 格式錯誤！請使用：球隊 vs 球隊, Over門檻, Under門檻, Over賠率, Under賠率")
                continue
            
            teams = parts[0]
            over_line = float(parts[1])
            under_line = float(parts[2])
            over_odds = float(parts[3])
            under_odds = float(parts[4])
            
            games.append({
                'teams': teams,
                'over_line': over_line,
                'under_line': under_line,
                'over_odds': over_odds,
                'under_odds': under_odds,
                'source': 'Manual Input'
            })
            
            print(f"✅ 已記錄: {teams}")
            
        except ValueError:
            print("❌ 數字格式錯誤！請檢查輸入。")
        except KeyboardInterrupt:
            print("\n\n⚠️ 使用者中斷輸入")
            break
    
    return games

# ==============================================================================
# 主要執行流程
# ==============================================================================

def main():
    print("🎯 === 台灣運彩 MLB 大小分賠率爬蟲 ===")
    print(f"📅 目標日期: {target_date}")
    print()
    
    all_games = []
    
    # 嘗試從各個來源抓取
    for source in ODDS_SOURCES:
        print(f"📡 嘗試從 {source['name']} 抓取數據...")
        
        url = source['url_template'].format(date=target_date)
        html_content = fetch_page(url)
        
        if html_content:
            try:
                games = eval(source['parser'])(html_content)
                if games:
                    all_games.extend(games)
                    print(f"✅ 從 {source['name']} 成功獲取 {len(games)} 場比賽")
                    break  # 如果成功就停止
                else:
                    print(f"⚠️ {source['name']} 沒有找到比賽數據")
            except Exception as e:
                print(f"❌ 解析 {source['name']} 數據時發生錯誤: {e}")
        else:
            print(f"❌ 無法從 {source['name']} 取得網頁內容")
        
        # 來源之間等待一段時間
        time.sleep(random.uniform(2, 5))
    
    # 如果自動爬蟲失敗，提供手動輸入
    if not all_games:
        print("\n⚠️ 所有自動來源都失敗，提供手動輸入選項")
        all_games = parse_manual_input()
    
    if not all_games:
        print("\n❌ 沒有取得任何比賽數據")
        return
    
    # 建立 DataFrame
    df_odds = pd.DataFrame(all_games)
    
    # 保存為 CSV
    csv_filename = os.path.join(OUTPUT_DIR, f'mlb_odds_{target_date}.csv')
    df_odds.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    print(f"\n💾 數據已保存到: {csv_filename}")
    
    # 顯示摘要
    print(f"\n📊 摘要:")
    print(f"   總比賽場數: {len(df_odds)}")
    print(f"   Over 門檻範圍: {df_odds['over_line'].min():.1f} - {df_odds['over_line'].max():.1f}")
    print(f"   Under 門檻範圍: {df_odds['under_line'].min():.1f} - {df_odds['under_line'].max():.1f}")
    print(f"   Over 賠率範圍: {df_odds['over_odds'].min():.2f} - {df_odds['over_odds'].max():.2f}")
    print(f"   Under 賠率範圍: {df_odds['under_odds'].min():.2f} - {df_odds['under_odds'].max():.2f}")
    
    # 顯示前 5 場比賽
    print(f"\n📋 前 5 場比賽:")
    for _, game in df_odds.head(5).iterrows():
        print(f"   {game['teams']}")
        print(f"     Over: {game['over_line']} @ {game['over_odds']}")
        print(f"     Under: {game['under_line']} @ {game['under_odds']}")
        print()
    
    # 生成 JSON 格式供網頁使用
    json_filename = os.path.join(OUTPUT_DIR, f'mlb_odds_{target_date}.json')
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(df_odds.to_dict('records'), f, ensure_ascii=False, indent=2)
    
    print(f"💾 JSON 格式已保存到: {json_filename}")
    
    # 提供後續整合建議
    print("\n" + "="*60)
    print("📝 下一步：")
    print("="*60)
    print("1. 將 CSV/JSON 檔案上傳到 GitHub")
    print("2. 在 GitHub Pages 上顯示賠率數據")
    print("3. 與你的預測模型整合")
    print()
    print("整合範例程式碼：")
    print("""
    # 讀取賠率數據
    import pandas as pd
    df_odds = pd.read_csv('odds_data/mlb_odds_2026-07-19.csv')
    
    # 與預測模型合併
    df_model = pd.read_csv('model_predictions.csv')
    df_combined = pd.merge(df_model, df_odds, left_on='teams', right_on='teams')
    
    # 計算 EV
    # ...（使用你現有的預測邏輯）
    """)
    
    return df_odds

if __name__ == "__main__":
    try:
        df_odds = main()
    except Exception as e:
        print(f"\n❌ 程式執行失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
