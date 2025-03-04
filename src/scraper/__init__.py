import requests
import requests_cache
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import math
import logging

# ログの設定
logging.basicConfig(level=logging.INFO)

# キャッシュを有効にする
requests_cache.install_cache('race_cache', expire_after=3600)

def scrape_race_data(url):
    with requests_cache.enabled():
        response = requests.get(url)
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 出馬表のデータを抽出
        table = soup.find('table', {'class': 'basic narrow-xy mt20'})
        if not table:
            logging.error('Table not found')
            return {'error': 'Table not found'}
        
        rows = table.find_all('tr')
        
        race_data = []
        horse_data = []
        for row in rows:
            cols = row.find_all('th')
            cols = [col.text.strip() for col in cols]
            race_data.append(cols)
            cols = row.find_all('td')
            cols = [col.text.strip() for col in cols]
            race_data.append(cols)
            
            # 馬番、馬名、オッズを抽出
            if len(cols) > 3:
                number = cols[1]
                name_div = row.find('div', class_='name')
                odds_div = row.find('span', class_='num')
                name = name_div.text.strip() if name_div else 'N/A'
                odds = odds_div.text.strip() if odds_div else 'N/A'
                
                # オッズが「除外」の場合は0に設定
                if odds == '除外' or odds == '取消':
                    odds = '0'
                
                # 過去4レースの情報を取得
                past_race_classes = ['past p1', 'past p2', 'past p3', 'past p4']
                past_race_urls = []
                past_race_times = []
                past_race_distances = []
                for past_race_class in past_race_classes:
                    past_races = row.find_all('td', class_=lambda x: x and past_race_class in x)
                    for past_race in past_races:
                        race_link = past_race.find('a', href=True)
                        race_time = past_race.find('p', class_='time')
                        if race_link and race_time:
                            time_text = race_time.text.strip()
                            if time_text:
                                try:
                                    if ':' in time_text:
                                        minutes, seconds = map(float, time_text.split(':'))
                                    else:
                                        minutes = 0
                                        seconds = float(time_text)
                                    past_race_times.append(minutes * 60 + seconds)
                                    past_race_urls.append(urljoin(url, race_link['href']))
                                except ValueError:
                                    # タイムのフォーマットが正しくない場合はスキップ
                                    logging.warning(f'Invalid time format: {time_text}')
                                    continue
                
                # 並列処理で各レースの偏差値を計算
                with ThreadPoolExecutor() as executor:
                    results = list(executor.map(scrape_race_times_and_prize, past_race_urls))
                
                z_scores = []
                prizes = []
                calculations = []  # 各レースの計算結果を保存するリスト
                for (other_times, prize, distance), race_time in zip(results, past_race_times):
                    if other_times and distance > 0:
                        speeds = [distance / t for t in other_times]
                        mean_speed = np.mean(speeds)
                        std_speed = np.std(speeds)
                        speed = distance / race_time
                        z_score = (speed - mean_speed) / std_speed if std_speed != 0 else 0
                        z_scores.append(z_score)
                        prizes.append(math.log(prize, 10))
                        #calculations.append(z_score)
                        calculations.append(prize * (10 ** (0.5 * z_score)))  # 計算結果を保存
                    else:
                        logging.warning(f'Missing data for race: times={other_times}, distance={distance}')
                
                # 過去のレース情報が4レースに満たない場合の処理
                '''
                if len(z_scores) < 4:
                    avg_z_score = np.mean(z_scores) if z_scores else 0
                    avg_prize = np.mean(prizes) if prizes else 0
                    while len(z_scores) < 4:
                        z_scores.append(avg_z_score)
                        prizes.append(avg_prize)
                '''
                
                # 仮の評価値を計算
                rating = sum(calculations)
                if 0 < len(z_scores) < 4:
                    rating = rating * 4 / len(z_scores)
                
                # 馬の期待値を計算
                expected_value = float(odds) * rating if odds != 'N/A' else 'N/A'
                
                # オッズが0の場合は評価値と期待値も0に設定
                if float(odds) == 0:
                    rating = 0
                    expected_value = 0
                
                horse_data.append({
                    'number': number,
                    'name': name,
                    'odds': odds,
                    'rating': rating,
                    'expected_value': expected_value,
                    'calculations': calculations  # 計算結果を保存
                })
    
    return race_data, horse_data

def scrape_race_times_and_prize(url):
    with requests_cache.enabled():
        response = requests.get(url, timeout=10)  # タイムアウトを設定
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # レースの距離を取得
        distance_div = soup.find('div', class_='cell course')
        distance = 0
        if distance_div:
            distance_text = distance_div.find('span', class_='cap').next_sibling.strip()
            distance = float(distance_text.replace(',', ''))
        
        # レース情報ページから他の馬の完走タイムを抽出
        times = []
        table = soup.find('table', {'class': 'basic narrow-xy striped'})
        if table:
            rows = table.find_all('tr')
            for row in rows:
                time_td = row.find('td', class_='time')
                if time_td:
                    time_text = time_td.text.strip()
                    if time_text:
                        try:
                            # タイムを秒数に変換
                            if ':' in time_text:
                                minutes, seconds = map(float, time_text.split(':'))
                            else:
                                minutes = 0
                                seconds = float(time_text)
                            time = minutes * 60 + seconds
                            times.append(time)
                        except ValueError:
                            # タイムのフォーマットが正しくない場合はスキップ
                            logging.warning(f'Invalid time format: {time_text}')
                            continue
        
        # 1着の賞金額を抽出
        prize = 0
        prize_list = soup.find('ul', class_='prize')
        if prize_list:
            first_prize = prize_list.find('span', text='1着').find_next('span', class_='num')
            if first_prize:
                if ',' in first_prize.text:
                    prize = float(first_prize.text.replace(',', ''))
                else:
                    prize = float(first_prize.text)
        
        return times, prize, distance