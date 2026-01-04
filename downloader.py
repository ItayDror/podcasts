import yt_dlp
import os

class PodcastDownloader:
    def __init__(self, output_dir="temp"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def download_audio(self, url):
        """
        Download audio from a URL (works with YouTube, podcast feeds, etc.)
        Returns: tuple of (file_path, title, duration_seconds, file_size_mb)
        """
        output_template = os.path.join(self.output_dir, '%(title)s.%(ext)s')

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"Downloading audio from: {url}")
                info = ydl.extract_info(url, download=True)

                # Get the output filename
                title = info.get('title', 'Unknown')
                duration = info.get('duration', 0)

                # Construct the expected filename
                filename = ydl.prepare_filename(info)
                # Replace the extension with mp3
                audio_file = os.path.splitext(filename)[0] + '.mp3'

                # Get file size in MB
                file_size_mb = os.path.getsize(audio_file) / (1024 * 1024)

                print(f"Downloaded: {title}")
                print(f"Duration: {duration} seconds ({duration/60:.1f} minutes)")
                print(f"File size: {file_size_mb:.2f} MB")

                return audio_file, title, duration, file_size_mb

        except Exception as e:
            print(f"Error downloading audio: {e}")
            raise

    def cleanup(self, file_path):
        """Delete the downloaded file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Cleaned up: {file_path}")
        except Exception as e:
            print(f"Error cleaning up file: {e}")
