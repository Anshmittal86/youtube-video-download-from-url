import streamlit as st
import yt_dlp
import os
import time
import threading
from dataclasses import dataclass
from typing import Optional

@dataclass
class DownloadProgress:
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    eta: int = 0
    percentage: float = 0.0
    status: str = "idle"

# Global progress tracker
progress_tracker = DownloadProgress()

def progress_hook(d):
    """Hook function to track download progress"""
    global progress_tracker
    
    if d['status'] == 'downloading':
        progress_tracker.status = "downloading"
        progress_tracker.downloaded_bytes = d.get('downloaded_bytes', 0)
        progress_tracker.total_bytes = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
        progress_tracker.speed = d.get('speed', 0) or 0
        progress_tracker.eta = d.get('eta', 0) or 0
        
        if progress_tracker.total_bytes > 0:
            progress_tracker.percentage = (progress_tracker.downloaded_bytes / progress_tracker.total_bytes) * 100
        else:
            progress_tracker.percentage = 0
            
    elif d['status'] == 'finished':
        progress_tracker.status = "finished"
        progress_tracker.percentage = 100.0
    elif d['status'] == 'error':
        progress_tracker.status = "error"

def get_video_info(url):
    """Extract video information without downloading"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

def get_available_formats(info):
    """Get available video formats"""
    formats = []
    seen_qualities = set()
    
    if 'formats' in info:
        for f in info['formats']:
            if f.get('vcodec') != 'none' and f.get('height'):
                quality = f.get('height')
                format_note = f.get('format_note', '')
                ext = f.get('ext', '')
                filesize = f.get('filesize')
                
                if quality not in seen_qualities and quality <= 1080:
                    seen_qualities.add(quality)
                    size_mb = f" ({filesize // (1024*1024)} MB)" if filesize else ""
                    formats.append({
                        'quality': f"{quality}p",
                        'format': ext.upper(),
                        'note': format_note,
                        'size': size_mb
                    })
    
    # Sort by quality (highest first)
    formats.sort(key=lambda x: int(x['quality'].replace('p', '')), reverse=True)
    return formats

def download_video(url, quality='best'):
    """Download video with specified quality"""
    global progress_tracker
    progress_tracker = DownloadProgress()
    
    # Format selection based on quality
    if quality == 'best':
        format_selector = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
    else:
        height = quality.replace('p', '')
        format_selector = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]'
    
    ydl_opts = {
        'format': format_selector,
        'merge_output_format': 'mp4',
        'outtmpl': '%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'progress_hooks': [progress_hook],
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4'
        }]
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).replace(".webm", ".mp4").replace(".mkv", ".mp4")
        return filename, info

def format_bytes(bytes_val):
    """Convert bytes to human readable format"""
    if bytes_val == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} TB"

def format_time(seconds):
    """Convert seconds to readable time format"""
    if seconds <= 0:
        return "Unknown"
    
    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

# Streamlit UI
st.set_page_config(page_title="YouTube Downloader", page_icon="🎥", layout="wide")

st.title("🎥 Enhanced YouTube Video Downloader")
st.markdown("Download videos in **MP4 format** with progress tracking")

# Create two columns for layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📥 Download Video")
    video_url = st.text_input("Paste YouTube Video URL", placeholder="https://www.youtube.com/watch?v=...")
    
    # Get video info button
    if st.button("🔍 Get Video Info", type="secondary"):
        if not video_url:
            st.warning("⚠️ Please enter a YouTube video URL.")
        else:
            with st.spinner("Fetching video information..."):
                try:
                    info = get_video_info(video_url)
                    st.session_state.video_info = info
                    st.success("✅ Video information loaded!")
                except Exception as e:
                    st.error(f"❌ Failed to fetch video info: {e}")

with col2:
    st.subheader("📋 Supported Formats")
    st.markdown("""
    **Video Formats:**
    - MP4 (H.264)
    - WebM (VP9)
    - MKV (H.264)
    
    **Quality Options:**
    - 1080p (Full HD)
    - 720p (HD)
    - 480p (SD)
    - 360p (Low)
    
    **Output:** Always MP4
    """)

# Display video info and download options
if hasattr(st.session_state, 'video_info'):
    info = st.session_state.video_info
    
    # Video preview
    st.subheader("🎬 Video Preview")
    video_col1, video_col2 = st.columns([1, 2])
    
    with video_col1:
        if info.get('thumbnail'):
            st.image(info['thumbnail'], width=200)
    
    with video_col2:
        st.markdown(f"**Title:** {info.get('title', 'Unknown')}")
        st.markdown(f"**Duration:** {format_time(info.get('duration', 0))}")
        st.markdown(f"**Uploader:** {info.get('uploader', 'Unknown')}")
        st.markdown(f"**Views:** {info.get('view_count', 'Unknown'):,}" if info.get('view_count') else "**Views:** Unknown")
    
    # Available formats
    st.subheader("🎯 Available Formats")
    formats = get_available_formats(info)
    
    if formats:
        format_display = []
        for fmt in formats:
            format_display.append(f"**{fmt['quality']}** - {fmt['format']}{fmt['size']}")
        
        format_cols = st.columns(min(len(formats), 4))
        for i, fmt_text in enumerate(format_display):
            with format_cols[i % 4]:
                st.markdown(fmt_text)
    
    # Quality selection
    st.subheader("⚙️ Download Options")
    quality_options = ["best"] + [f"{fmt['quality']}" for fmt in formats]
    selected_quality = st.selectbox("Select Quality:", quality_options)
    
    # Download button
    if st.button("🚀 Start Download", type="primary"):
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        # Start download in a separate thread
        download_thread = threading.Thread(
            target=lambda: download_video(video_url, selected_quality),
            daemon=True
        )
        
        try:
            download_thread.start()
            
            # Progress tracking loop
            while download_thread.is_alive() or progress_tracker.status == "downloading":
                with progress_placeholder.container():
                    if progress_tracker.status == "downloading":
                        # Progress bar
                        progress_bar = st.progress(progress_tracker.percentage / 100)
                        
                        # Progress info
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Progress", f"{progress_tracker.percentage:.1f}%")
                        with col2:
                            st.metric("Speed", f"{format_bytes(progress_tracker.speed)}/s" if progress_tracker.speed else "Calculating...")
                        with col3:
                            st.metric("ETA", format_time(progress_tracker.eta))
                        
                        # Downloaded/Total size
                        if progress_tracker.total_bytes > 0:
                            st.write(f"Downloaded: {format_bytes(progress_tracker.downloaded_bytes)} / {format_bytes(progress_tracker.total_bytes)}")
                
                time.sleep(0.5)
            
            # Download completed
            if progress_tracker.status == "finished":
                file_path, _ = download_video(video_url, selected_quality)
                status_placeholder.success("✅ Video downloaded successfully!")
                
                # Download button
                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        st.download_button(
                            label="📥 Click to Download MP4",
                            data=f,
                            file_name=os.path.basename(file_path),
                            mime="video/mp4",
                            use_container_width=True
                        )
            
        except Exception as e:
            status_placeholder.error(f"❌ Download failed: {e}")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎥 Enhanced YouTube Video Downloader with Progress Tracking</p>
    <p>Supports YouTube, Vimeo, and many other video platforms</p>
</div>
""", unsafe_allow_html=True)

