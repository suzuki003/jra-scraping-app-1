import os
from flask import Flask, request, jsonify, render_template, url_for
from scraper import scrape_race_data, scrape_jra_races

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['GET'])
def scrape():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        race_data, horse_data = scrape_race_data(url)
        if 'error' in race_data:
            return jsonify(race_data), 500
        
        return render_template('race_data.html', race_data=race_data, horse_data=horse_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/race_selection')
def race_selection():
    # JRAの公式サイトからレース情報をスクレイピング
    race_data = scrape_jra_races()
    return render_template('race_selection.html', races=race_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)