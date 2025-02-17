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


def calculate_bitrate(duration, width, height, target_size_mb=9, audio_bitrate_kb=128):
    try:
        # Calculate target size in bits
        target_size_bits = target_size_mb * 8 * 1024 * 1024
        audio_size_bits = duration * audio_bitrate_kb * 1024

        # Reduce overhead margin to just 1%
        available_bits = target_size_bits * 0.99 - audio_size_bits

        # Calculate video bitrate
        video_bitrate_kb = int(available_bits / (duration * 1024))

        # Adjust bitrate based on resolution with a more aggressive scale
        resolution = width * height
        if resolution <= 1280 * 720:  # 720p or less
            resolution_factor = 0.9
        elif resolution <= 1920 * 1080:  # 1080p
            resolution_factor = 1.1
        else:  # 2K/4K
            resolution_factor = 1.3

        video_bitrate_kb = int(video_bitrate_kb * resolution_factor)

        # Higher minimum bitrates to prevent over-compression
        min_bitrate = {
            1280 * 720: 2000,  # 720p minimum 2000Kbps
            1920 * 1080: 3000,  # 1080p minimum 3000Kbps
            2560 * 1440: 4000,  # 2K minimum 4000Kbps
            3840 * 2160: 6000,  # 4K minimum 6000Kbps
        }

        # Find appropriate minimum bitrate
        min_bitrate_kb = 2000  # higher default minimum
        for res, bitrate in sorted(min_bitrate.items()):
            if resolution <= res:
                min_bitrate_kb = bitrate
                break

        # Calculate target bitrate based on duration
        target_bitrate_kb = int((target_size_bits * 0.99) / (duration * 1024))

        # Set maximum bitrate higher for short videos
        if duration < 60:
            max_bitrate_kb = min(16000, target_bitrate_kb * 1.2)
        else:
            max_bitrate_kb = min(12000, target_bitrate_kb)

        # Apply limits but favor higher quality
        video_bitrate_kb = min(max_bitrate_kb, max(min_bitrate_kb, video_bitrate_kb))

        # For very short videos, ensure we use more of the available space
        if duration < 30:
            video_bitrate_kb = max(video_bitrate_kb, target_bitrate_kb * 0.9)

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
