#!/usr/bin/env python3
"""
Podcast Transcriber - Download and transcribe podcasts using Whisper AI
"""

import argparse
import os
import sys
from downloader import PodcastDownloader
from transcriber import AudioTranscriber
from database import TranscriptDatabase

def main():
    parser = argparse.ArgumentParser(
        description='Download and transcribe podcasts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Transcribe a YouTube video
  python3 transcribe_podcast.py "https://www.youtube.com/watch?v=VIDEO_ID"

  # Use a different Whisper model (base is default)
  python3 transcribe_podcast.py "URL" --model small

  # Include timestamps in the transcript
  python3 transcribe_podcast.py "URL" --timestamps

Available Whisper models (accuracy vs speed):
  tiny   - Fastest, least accurate (~1GB RAM)
  base   - Fast, decent accuracy (~1GB RAM) [DEFAULT]
  small  - Good balance (~2GB RAM)
  medium - Better accuracy (~5GB RAM)
  large  - Best accuracy (~10GB RAM)
        '''
    )

    parser.add_argument(
        'url',
        nargs='?',
        help='URL of the podcast/video to transcribe'
    )

    parser.add_argument(
        '--model',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        default='base',
        help='Whisper model size (default: base)'
    )

    parser.add_argument(
        '--timestamps',
        action='store_true',
        help='Include timestamps in the transcript'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='List all previous transcriptions'
    )

    parser.add_argument(
        '--search',
        type=str,
        help='Search transcripts for a keyword'
    )

    args = parser.parse_args()

    # Initialize database
    db = TranscriptDatabase()

    # Handle list command
    if args.list:
        transcripts = db.get_all_transcripts()
        if not transcripts:
            print("No transcripts found in database.")
        else:
            print(f"\nFound {len(transcripts)} transcript(s):\n")
            for t in transcripts:
                print(f"ID: {t[0]}")
                print(f"Title: {t[2]}")
                print(f"URL: {t[1]}")
                print(f"Date: {t[3]}")
                print("-" * 50)
        return

    # Handle search command
    if args.search:
        results = db.search_transcripts(args.search)
        if not results:
            print(f"No transcripts found containing '{args.search}'")
        else:
            print(f"\nFound {len(results)} transcript(s) containing '{args.search}':\n")
            for r in results:
                print(f"ID: {r[0]}")
                print(f"Title: {r[2]}")
                print(f"URL: {r[1]}")
                print(f"Date: {r[3]}")
                print("-" * 50)
        return

    # Require URL for transcription
    if not args.url:
        parser.print_help()
        sys.exit(1)

    print("=" * 60)
    print("PODCAST TRANSCRIBER")
    print("=" * 60)

    # Check if already transcribed
    existing = db.get_transcript_by_url(args.url)
    if existing:
        print(f"\nThis URL has already been transcribed on {existing[6]}")
        response = input("Transcribe again? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Exiting...")
            return

    downloader = PodcastDownloader()
    audio_file = None

    transcript_id = None

    try:
        # Step 1: Download audio
        print("\n[1/3] Downloading audio...")
        audio_file, title, duration, file_size_mb = downloader.download_audio(args.url)

        # Step 2: Transcribe
        print(f"\n[2/3] Transcribing with Whisper ({args.model} model)...")
        transcriber = AudioTranscriber(model_size=args.model)

        if args.timestamps:
            result = transcriber.transcribe_with_timestamps(audio_file)
        else:
            result = transcriber.transcribe(audio_file)

        transcript_text = result['text']

        print(f"\nDetected language: {result.get('language', 'unknown')}")
        print(f"Transcript length: {len(transcript_text)} characters")

        # Step 3: Save to database as safety net
        print("\n[3/3] Saving to database...")
        transcript_id = db.save_transcript(
            url=args.url,
            title=title,
            transcript=transcript_text,
            duration_seconds=duration,
            model_used=args.model,
            file_size_mb=file_size_mb
        )

        # Verify the transcript file was created, then clean up DB row and audio
        base_name = os.path.splitext(os.path.basename(audio_file))[0]
        suffix = "_timestamped" if args.timestamps else ""
        transcript_file = os.path.join("transcripts", f"{base_name}{suffix}.md")

        if os.path.exists(transcript_file):
            db.delete_transcript(transcript_id)
            downloader.cleanup(audio_file)
            audio_file = None
            print(f"\nSuccess! Transcript saved to: {transcript_file}")
        else:
            print(f"\nWarning: transcript file not found at {transcript_file}")
            print("Keeping database row and audio file as backup.")

        # Show a preview
        print("\n" + "=" * 60)
        print("TRANSCRIPT PREVIEW (first 500 characters)")
        print("=" * 60)
        print(transcript_text[:500] + "..." if len(transcript_text) > 500 else transcript_text)
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n\nTranscription cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        if transcript_id:
            print("Transcript is preserved in the database.")
        sys.exit(1)

    print("\nAll done!")

if __name__ == "__main__":
    main()
