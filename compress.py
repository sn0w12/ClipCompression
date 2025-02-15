import sys
import json
import subprocess
import os
from pathlib import Path


def get_video_info(input_path, start_time=None, duration=None):
    try:
        # Check if file exists
        if not os.path.exists(input_path):
            raise Exception(f"Input file not found: {input_path}")

        # First get stream info
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-show_entries",
            "stream=width,height,r_frame_rate",  # Added r_frame_rate
            "-select_streams",
            "v:0",
            "-of",
            "json",
            str(input_path),
        ]

        # Print command for debugging
        print(f"Running command: {' '.join(cmd)}", file=sys.stderr)

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            raise Exception(f"ffprobe failed with error: {result.stderr}")

        info = json.loads(result.stdout)

        # Get full duration from format section
        full_duration = float(info.get("format", {}).get("duration", 0))
        if full_duration == 0:
            raise Exception("Could not determine video duration")

        # Calculate actual duration based on start_time and duration parameters
        start_seconds = float(start_time) if start_time else 0
        if start_seconds >= full_duration:
            raise Exception("Start time is beyond video duration")

        if duration:
            clip_duration = min(float(duration), full_duration - start_seconds)
        else:
            clip_duration = full_duration - start_seconds

        # Get video dimensions from first video stream
        streams = info.get("streams", [])
        if not streams:
            raise Exception("No video streams found")

        width = int(streams[0].get("width", 0))
        height = int(streams[0].get("height", 0))
        frame_rate = streams[0].get("r_frame_rate", "30/1")
        try:
            num, den = map(int, frame_rate.split("/"))
            fps = num / den
        except:
            fps = 30

        if width == 0 or height == 0:
            raise Exception("Could not determine video dimensions")

        return clip_duration, width, height, fps

    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse ffprobe output: {e}")
    except Exception as e:
        raise Exception(f"Error in get_video_info: {str(e)}")


def calculate_bitrate(duration, width, height, target_size_mb=10, audio_bitrate_kb=128):
    try:
        # Calculate target size in bits
        target_size_bits = target_size_mb * 8 * 1024 * 1024
        audio_size_bits = duration * audio_bitrate_kb * 1024

        # Leave headroom for container overhead
        available_bits = target_size_bits * 0.95 - audio_size_bits

        # Calculate video bitrate
        video_bitrate_kb = int(available_bits / (duration * 1024))

        # Adjust bitrate based on resolution
        resolution_factor = (width * height) / (1920 * 1080)
        video_bitrate_kb = int(video_bitrate_kb * min(resolution_factor, 1.5))

        # Set minimum and maximum bitrates
        video_bitrate_kb = max(video_bitrate_kb, 500)  # minimum 500Kbps
        video_bitrate_kb = min(video_bitrate_kb, 8000)  # maximum 8000Kbps

        return video_bitrate_kb

    except Exception as e:
        raise Exception(f"Error in calculate_bitrate: {str(e)}")


def main():
    try:
        if len(sys.argv) < 2:
            print(
                "Usage: python compress.py <input_video> [start_seconds] [duration_seconds]",
                file=sys.stderr,
            )
            sys.exit(1)

        input_path = Path(sys.argv[1])

        # Parse time parameters as simple numbers
        start_time = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
        duration = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None

        # Get video information
        print(f"Analyzing video: {input_path}", file=sys.stderr)
        duration, width, height, fps = get_video_info(input_path, start_time, duration)

        # Calculate bitrate
        print(
            f"Duration: {duration:.2f}s, Resolution: {width}x{height}", file=sys.stderr
        )
        video_bitrate = calculate_bitrate(duration, width, height)

        # Output just the bitrate for the batch script
        should_reduce_fps = fps > 30
        print(f"{video_bitrate} {1 if should_reduce_fps else 0}")

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
