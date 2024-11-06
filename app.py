from flask import Flask, request, send_file, render_template, jsonify, session
import yt_dlp
import os
from urllib.parse import urlparse
import re
import time
import requests
import json
from translations import translations
import shutil
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_TYPE'] = 'filesystem'

def get_douyin_cookies():
    """Get fresh cookies for Douyin"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    session = requests.Session()
    session.get('https://www.douyin.com/', headers=headers)
    cookie_string = '; '.join([f'{cookie.name}={cookie.value}' for cookie in session.cookies])
    
    return cookie_string, headers

def clean_douyin_url(url):
    """Clean and convert Douyin URLs to a format yt-dlp can handle"""
    if 'douyin.com' in url or 'iesdouyin.com' in url:
        # Handle discover URLs
        if '/discover?' in url:
            modal_id = re.search(r'modal_id=(\d+)', url)
            if modal_id:
                return f'https://www.douyin.com/video/{modal_id.group(1)}'
        
        # Handle note URLs
        if '/note/' in url:
            note_id = url.split('/note/')[-1].split('/')[0]
            return f'https://www.douyin.com/note/{note_id}'
            
        # Handle video URLs
        if '/video/' in url:
            video_id = url.split('/video/')[-1].split('/')[0].split('?')[0]
            return f'https://www.douyin.com/video/{video_id}'
            
        # Extract modal_id from any URL format
        modal_match = re.search(r'modal_id=(\d+)', url)
        if modal_match:
            return f'https://www.douyin.com/video/{modal_match.group(1)}'

    return url

def get_yt_dlp_opts(base_opts=None):
    """Get yt-dlp options with necessary cookies and headers"""
    opts = base_opts or {}
    
    # Get fresh cookies and headers for Douyin
    cookie_string, headers = get_douyin_cookies()
    
    # Update options with cookies and headers
    opts.update({
        'http_headers': headers,
        'cookies': cookie_string
    })
    
    return opts

@app.route('/')
def index():
    # Get language from session or default to English
    lang = session.get('lang', 'en')
    return render_template('index.html', translations=translations[lang])

@app.route('/set-language', methods=['POST'])
def set_language():
    data = request.get_json()
    lang = data.get('lang', 'en')
    if lang in translations:
        session['lang'] = lang
        return jsonify(translations[lang])
    return jsonify({'error': 'Language not supported'}), 400

@app.route('/check-video', methods=['POST'])
def check_video():
    try:
        data = request.get_json()
        url = data.get('url')

        if not is_valid_url(url):
            return jsonify({'error': 'Invalid URL format'}), 400

        if not validate_video_url(url):
            return jsonify({'error': 'URL must be from YouTube, TikTok, or Douyin'}), 400

        url = clean_douyin_url(url)
        ydl_opts = get_yt_dlp_opts({
            'quiet': True,
            'no_warnings': True,
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title', ''),
                'author': info.get('uploader', ''),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0)
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

def cleanup_downloads():
    """Clean up files older than 1 hour"""
    if os.path.exists('downloads'):
        current_time = datetime.now()
        for filename in os.listdir('downloads'):
            filepath = os.path.join('downloads', filename)
            file_time = datetime.fromtimestamp(os.path.getctime(filepath))
            if current_time - file_time > timedelta(hours=1):
                try:
                    os.remove(filepath)
                except:
                    pass

@app.route('/download', methods=['POST'])
def download():
    try:
        # Clean up old files first
        cleanup_downloads()
        
        data = request.get_json()
        url = data.get('url')
        quality = data.get('quality', 'normal')

        if not is_valid_url(url):
            return jsonify({'error': 'Invalid URL format'}), 400

        if not validate_video_url(url):
            return jsonify({'error': 'URL must be from YouTube, TikTok, or Douyin'}), 400

        url = clean_douyin_url(url)

        if not os.path.exists('downloads'):
            os.makedirs('downloads')

        timestamp = int(time.time())
        base_filename = f'downloads/video_{timestamp}'

        # Configure quality-specific options
        if quality == 'audio':
            base_opts = {
                'format': 'bestaudio',
                'outtmpl': f'{base_filename}.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'prefer_ffmpeg': True,
                'keepvideo': False
            }
            final_extension = '.mp3'
        elif quality == 'hd':
            base_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': f'{base_filename}.%(ext)s',
                'merge_output_format': 'mp4'
            }
            final_extension = '.mp4'
        else:
            base_opts = {
                'format': 'best[height<=480][ext=mp4]/best[height<=480]/best[ext=mp4]/best',
                'outtmpl': f'{base_filename}.%(ext)s',
            }
            final_extension = '.mp4'

        # Get complete options with cookies and headers
        ydl_opts = get_yt_dlp_opts(base_opts)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            return jsonify({'error': f'Download failed: {str(e)}'}), 500

        output_file = f'{base_filename}{final_extension}'
        
        time.sleep(1)
        
        if os.path.exists(output_file):
            try:
                return_value = send_file(
                    output_file,
                    as_attachment=True,
                    download_name=f'video{final_extension}'
                )
                # Delete file after sending
                os.remove(output_file)
                return return_value
            except Exception as e:
                return jsonify({'error': f'Error sending file: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Output file not found'}), 500

    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

def is_valid_url(url):
    try:
        # Handle URLs that start with mobile.
        if url.startswith('mobile.'):
            url = 'https://' + url[7:]
        
        # Add https:// if no scheme is present
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        result = urlparse(url)
        return bool(result.scheme and result.netloc)
    except:
        return False

def validate_video_url(url):
    valid_domains = [
        'youtube.com', 
        'youtu.be', 
        'tiktok.com',
        'douyin.com',
        'iesdouyin.com',
        'vm.tiktok.com',  # Short TikTok URLs
        'm.tiktok.com',   # Mobile TikTok URLs
        'vt.tiktok.com',  # Another TikTok URL format
        'www.youtube.com',
        'www.tiktok.com',
        'www.douyin.com',
    ]
    try:
        # Handle URLs that start with mobile.
        if url.startswith('mobile.'):
            url = 'https://' + url[7:]
            
        # Add https:// if no scheme is present
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # For Douyin discover URLs
        if 'douyin.com/discover' in url and 'modal_id=' in url:
            return True

        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # Remove 'www.' from domain for comparison
        if domain.startswith('www.'):
            domain = domain[4:]
            
        return any(valid_domain.replace('www.', '') in domain for valid_domain in valid_domains)
    except:
        return False

if __name__ == '__main__':
    app.run(debug=True)