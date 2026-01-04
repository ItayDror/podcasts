# Podcast Transcriber

Automatically download and transcribe podcasts using OpenAI's Whisper AI. This tool downloads audio from various sources (YouTube, podcast feeds, etc.), transcribes them using state-of-the-art AI, and stores the transcripts in a local database.

## Features

- Download audio from YouTube, podcast feeds, and other sources
- Transcribe using OpenAI Whisper (multiple model sizes available)
- Automatically cleanup downloaded files after transcription
- Store transcripts in a local SQLite database
- Search through past transcripts
- Optional timestamps in transcripts
- Works completely offline (after initial setup)

## Prerequisites

Before you begin, you need to install:

1. **Python 3.8+**
2. **ffmpeg** (required for audio processing)

### Installing ffmpeg on macOS

Open Terminal and run:

```bash
# If you have Homebrew installed:
brew install ffmpeg

# If you don't have Homebrew, install it first:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
# Then install ffmpeg:
brew install ffmpeg
```

## Installation

1. **Clone this repository and navigate to the project folder:**

```bash
git clone <your-repo-url>
cd podcast-transcriber
```

2. **Create a virtual environment (recommended):**

```bash
python3 -m venv venv
source venv/bin/activate
```

You'll see `(venv)` appear in your terminal prompt when the virtual environment is active.

3. **Install Python dependencies:**

```bash
pip install -r requirements.txt
```

This will install:
- `openai-whisper` - AI transcription engine
- `yt-dlp` - Audio downloader (works with YouTube and many other sites)
- `python-dotenv` - Environment configuration

**Note:** The first time you run the transcriber, Whisper will download its AI model (~150MB for the base model). This only happens once.

## Usage

### Basic Transcription

```bash
# Transcribe a YouTube video
python3 transcribe_podcast.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Transcribe any supported audio/video URL
python3 transcribe_podcast.py "https://example.com/podcast-episode.mp3"
```

### Advanced Options

```bash
# Use a larger, more accurate model (takes longer)
python3 transcribe_podcast.py "URL" --model small

# Include timestamps for each segment
python3 transcribe_podcast.py "URL" --timestamps

# Use the most accurate model (requires more RAM and time)
python3 transcribe_podcast.py "URL" --model large
```

### Available Models

| Model | Speed | Accuracy | RAM Required |
|-------|-------|----------|--------------|
| tiny | Fastest | Basic | ~1GB |
| base | Fast | Good | ~1GB (default) |
| small | Medium | Better | ~2GB |
| medium | Slow | Great | ~5GB |
| large | Slowest | Best | ~10GB |

**Recommendation:** Start with `base` (default). If accuracy is poor, try `small` or `medium`.

### Managing Transcripts

```bash
# List all transcripts in the database
python3 transcribe_podcast.py --list

# Search transcripts for a keyword
python3 transcribe_podcast.py --search "keyword"
```

## What Happens When You Run It

1. **Download:** The audio is downloaded to the `temp/` folder
2. **Transcribe:** Whisper converts speech to text
3. **Save:** Transcript is saved to:
   - Database: `transcripts.db` (SQLite database)
   - Text file: `transcripts/[title].txt`
4. **Cleanup:** Downloaded audio file is automatically deleted

## Project Structure

```
podcast-transcriber/
├── transcribe_podcast.py  # Main script (run this)
├── downloader.py          # Handles audio downloading
├── transcriber.py         # Handles AI transcription
├── database.py            # Handles database operations
├── requirements.txt       # Python dependencies
├── transcripts.db         # SQLite database (created automatically)
├── transcripts/           # Folder with saved transcript files
└── temp/                  # Temporary folder for downloads (auto-cleaned)
```

## Example Workflow

1. Open Terminal
2. Navigate to the project:
   ```bash
   cd podcast-transcriber
   ```
3. Activate virtual environment (if you created one):
   ```bash
   source venv/bin/activate
   ```
4. Run the transcriber:
   ```bash
   python3 transcribe_podcast.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
   ```
5. Wait for it to complete (progress will be shown)
6. Find your transcript in the `transcripts/` folder

## Troubleshooting

### "ffmpeg not found"
Install ffmpeg using the instructions in the Prerequisites section above.

### "Module not found" errors
Make sure you've installed the requirements:
```bash
pip install -r requirements.txt
```

### Transcription is very slow
- Try using the `tiny` or `base` model (default)
- Longer podcasts take proportionally longer
- First run downloads the AI model (~150MB)

### Out of memory errors
Use a smaller model:
```bash
python3 transcribe_podcast.py "URL" --model tiny
```

## Tips

- The first transcription will take longer as Whisper downloads its model
- Transcription time is roughly 1/10 of the audio length (10-minute podcast = ~1 minute to transcribe with base model)
- Timestamps add minimal processing time
- The database remembers URLs you've already transcribed
- All processing happens locally - no data is sent to external services

## Database Location

Your transcripts are stored in:
- **Database file:** `transcripts.db` (in the project folder)
- **Text files:** `transcripts/` (in the project folder)

You can back these up to keep your transcripts safe.

## Deactivating Virtual Environment

When you're done, deactivate the virtual environment:
```bash
deactivate
```

## Next Steps

Once you're comfortable with the basics, you could:
- Schedule automatic transcriptions using cron
- Build a web interface
- Export transcripts to different formats
- Add speaker diarization (identify different speakers)

## Support

For issues or questions, refer to the documentation of:
- [OpenAI Whisper](https://github.com/openai/whisper)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
