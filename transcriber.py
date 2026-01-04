import whisper
import os

class AudioTranscriber:
    def __init__(self, model_size="base"):
        """
        Initialize the transcriber with a Whisper model

        Model sizes:
        - tiny: Fastest, least accurate (~1GB RAM)
        - base: Fast, decent accuracy (~1GB RAM) - DEFAULT
        - small: Good balance (~2GB RAM)
        - medium: Better accuracy (~5GB RAM)
        - large: Best accuracy (~10GB RAM)
        """
        self.model_size = model_size
        print(f"Loading Whisper {model_size} model...")
        self.model = whisper.load_model(model_size)
        print("Model loaded successfully!")

    def transcribe(self, audio_file_path, save_to_file=True, output_dir="transcripts"):
        """
        Transcribe an audio file

        Returns: dict with 'text' and 'segments' keys
        """
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        print(f"Transcribing: {audio_file_path}")
        print("This may take a while depending on the audio length...")

        # Transcribe the audio
        result = self.model.transcribe(audio_file_path)

        transcript_text = result["text"]

        # Optionally save to a text file
        if save_to_file:
            os.makedirs(output_dir, exist_ok=True)
            base_name = os.path.splitext(os.path.basename(audio_file_path))[0]
            output_file = os.path.join(output_dir, f"{base_name}.txt")

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Transcript\n")
                f.write(f"{'=' * 50}\n\n")
                f.write(transcript_text)
                f.write(f"\n\n{'=' * 50}\n")
                f.write(f"Transcribed with Whisper ({self.model_size} model)\n")

            print(f"Transcript saved to: {output_file}")

        return {
            'text': transcript_text,
            'segments': result.get('segments', []),
            'language': result.get('language', 'unknown')
        }

    def transcribe_with_timestamps(self, audio_file_path, output_dir="transcripts"):
        """
        Transcribe with timestamps for each segment

        Returns: dict with full transcript and timestamped segments
        """
        result = self.transcribe(audio_file_path, save_to_file=False)

        # Create a formatted transcript with timestamps
        formatted_transcript = []
        for segment in result['segments']:
            start_time = self._format_timestamp(segment['start'])
            end_time = self._format_timestamp(segment['end'])
            text = segment['text'].strip()
            formatted_transcript.append(f"[{start_time} -> {end_time}] {text}")

        full_formatted = "\n".join(formatted_transcript)

        # Save to file
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(audio_file_path))[0]
        output_file = os.path.join(output_dir, f"{base_name}_timestamped.txt")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Transcript with Timestamps\n")
            f.write(f"{'=' * 50}\n\n")
            f.write(full_formatted)
            f.write(f"\n\n{'=' * 50}\n")
            f.write(f"Transcribed with Whisper ({self.model_size} model)\n")

        print(f"Timestamped transcript saved to: {output_file}")

        return {
            'text': result['text'],
            'formatted_with_timestamps': full_formatted,
            'segments': result['segments'],
            'language': result['language']
        }

    @staticmethod
    def _format_timestamp(seconds):
        """Convert seconds to HH:MM:SS format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
