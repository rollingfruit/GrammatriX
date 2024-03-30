
from flask import Flask, jsonify, send_from_directory
import time
import os

app = Flask(__name__, static_folder='../frontend')

@app.route('/message')
def get_message():
    time.sleep(3)
    return jsonify({'message': 'Hello from Flask!'})

@app.route('/')
def serve_vue_app():
    return send_from_directory(app.static_folder, 'index.html')

# 服务其他静态文件
@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    app.run(debug=True, port=8080)
