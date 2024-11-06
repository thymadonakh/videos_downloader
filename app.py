from flask import Flask, request, send_file, render_template, jsonify, session
import yt_dlp
import os
from urllib.parse import urlparse
import re
import time

app = Flask(__name__)
app.secret_key = os.urandom(24)

def is_valid_url(url):
    try:
        # Clean the URL
        url = url.strip()
        
        # Print for debugging
        print(f"Checking URL: {url}")
        
        # Handle URLs that start with mobile.
        if url.startswith('mobile.'):
            url = 'https://' + url[7:]
        
        # Add https:// if no scheme is present
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        result = urlparse(url)
        return bool(result.scheme and result.netloc)
    except Exception as e:
        print(f"URL validation error: {str(e)}")
        return False

def validate_video_url(url):
    try:
        # Print for debugging
        print(f"Validating URL: {url}")
        
        valid_patterns = [
            r'youtube\.com/watch\?v=',
            r'youtu\.be/',
            r'tiktok\.com/',
            r'douyin\.com/',
            r'vm\.tiktok\.com/',
            r'vt\.tiktok\.com/'
        ]
        
        # Check if URL matches any valid pattern
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in valid_patterns)
    except Exception as e:
        print(f"Video URL validation error: {str(e)}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check-video', methods=['POST'])
def check_video():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        # Debug prints
        print(f"Received URL: {url}")

        if not url:
            return jsonify({'error': 'Please enter a URL'}), 400

        if not is_valid_url(url):
            return jsonify({'error': 'Invalid URL format. Please check the URL and try again.'}), 400

        if not validate_video_url(url):
            return jsonify({'error': 'URL must be from YouTube, TikTok, or Douyin'}), 400

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_info': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return jsonify({
                    'title': info.get('title', ''),
                    'author': info.get('uploader', ''),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0)
                })
        except Exception as e:
            print(f"yt-dlp error: {str(e)}")
            return jsonify({'error': 'Could not process video. Please check the URL.'}), 400

    except Exception as e:
        print(f"General error: {str(e)}")
        return jsonify({'error': str(e)}), 400

@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        quality = data.get('quality', 'normal')

        print(f"Download request - URL: {url}, Quality: {quality}")

        if not url:
            return jsonify({'error': 'Please enter a URL'}), 400

        if not is_valid_url(url):
            return jsonify({'error': 'Invalid URL format'}), 400

        if not validate_video_url(url):
            return jsonify({'error': 'URL must be from YouTube, TikTok, or Douyin'}), 400

        # Configure format based on quality selection
        if quality == 'audio':
            format_opt = 'bestaudio/best'
            ext = '.mp3'
        elif quality == 'hd':
            format_opt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            ext = '.mp4'
        else:
            format_opt = 'best[height<=480][ext=mp4]/best[height<=480]/best[ext=mp4]/best'
            ext = '.mp4'

        timestamp = int(time.time())
        output_template = f'downloads/video_{timestamp}{ext}'

        ydl_opts = {
            'format': format_opt,
            'outtmpl': output_template,
            'quiet': False
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
                if os.path.exists(output_template):
                    return send_file(
                        output_template,
                        as_attachment=True,
                        download_name=f'video{ext}'
                    )
                else:
                    return jsonify({'error': 'Download failed'}), 500
        except Exception as e:
            print(f"Download error: {str(e)}")
            return jsonify({'error': 'Download failed. Please try again.'}), 500

    except Exception as e:
        print(f"General download error: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    app.run(debug=True)