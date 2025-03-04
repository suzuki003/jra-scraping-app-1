import os
from flask import Flask, request, jsonify, render_template
from scraper import scrape_race_data

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)