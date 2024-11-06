from flask import Flask, request, send_file, render_template, jsonify
import yt_dlp
import os
from urllib.parse import urlparse
import re
import time

app = Flask(__name__)

def is_valid_url(url):
    try:
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        result = urlparse(url)
        return bool(result.scheme and result.netloc)
    except:
        return False

def validate_video_url(url):
    valid_patterns = [
        r'youtube\.com/watch\?v=',
        r'youtu\.be/',
        r'tiktok\.com/',
        r'douyin\.com/',
        r'vm\.tiktok\.com/',
        r'vt\.tiktok\.com/'
    ]
    return any(re.search(pattern, url, re.IGNORECASE) for pattern in valid_patterns)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check-video', methods=['POST'])
def check_video():
    try:
        url = request.get_json().get('url', '').strip()

        if not url or not is_valid_url(url) or not validate_video_url(url):
            return jsonify({'error': 'Invalid URL'}), 400

        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title', ''),
                'author': info.get('uploader', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0)
            })
    except:
        return jsonify({'error': 'Could not process video'}), 400

@app.route('/download', methods=['POST'])
def download():
    try:
        url = request.get_json().get('url', '').strip()
        quality = request.get_json().get('quality', 'normal')

        if not url or not is_valid_url(url) or not validate_video_url(url):
            return jsonify({'error': 'Invalid URL'}), 400

        if quality == 'audio':
            format_opt = 'bestaudio/best'
            ext = '.mp3'
        elif quality == 'hd':
            format_opt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
            ext = '.mp4'
        else:
            format_opt = 'best[height<=480]/best'
            ext = '.mp4'

        output_file = f'downloads/video_{int(time.time())}{ext}'
        
        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        ydl_opts = {
            'format': format_opt,
            'outtmpl': output_file
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            if os.path.exists(output_file):
                return send_file(output_file, as_attachment=True)
            return jsonify({'error': 'Download failed'}), 500
    except:
        return jsonify({'error': 'Download failed'}), 500

if __name__ == '__main__':
    app.run()