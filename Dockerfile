FROM python:3.11-slim

# Install ffmpeg (required by yt-dlp and faster-whisper)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create necessary directories
RUN mkdir -p temp transcripts sessions

CMD ["python", "-m", "bot.main"]
