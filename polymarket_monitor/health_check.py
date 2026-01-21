"""
Health check endpoint for Cloud Run
Required to keep the container alive
"""
from flask import Flask, jsonify
import os
from datetime import datetime

app = Flask(__name__)

# Store bot status
bot_status = {
    'started_at': datetime.now().isoformat(),
    'status': 'running',
    'mode': os.getenv('BOT_MODE', 'semi')
}


@app.route('/')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'polymarket-whale-bot',
        'timestamp': datetime.now().isoformat(),
        **bot_status
    })


@app.route('/status')
def status():
    """Detailed status"""
    return jsonify(bot_status)


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
