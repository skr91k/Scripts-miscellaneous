#!/bin/bash

# Process screen recordings for Instagram Reels
# - Pulls recordings from Android device via ADB
# - Crops bottom navigation bar
# - Speeds up to 19 seconds
# - Adds padding for 9:16 aspect ratio
# - Adds background audio from source file with random start offset

INPUT_DIR="$HOME/Downloads/asr"
OUTPUT_DIR="$HOME/Downloads/asr/processed"
ANDROID_SCREEN_RECORDINGS="/sdcard/DCIM/Screen recordings"
CROP_BOTTOM=130  # Samsung nav bar height in pixels
TARGET_DURATION=19
mkdir -p "$INPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Audio source file
AUDIO_SOURCE="$HOME/Yeat - Money So Big (Instrumental⧸TikTok Remix) [LuvQfwoUC6w].mp4"

if [ -z "$AUDIO_SOURCE" ] || [ ! -f "$AUDIO_SOURCE" ]; then
    echo "Warning: No MP4 file found in ~/Downloads for audio"
    echo "Videos will be processed without background audio."
    AUDIO_AVAILABLE=false
else
    AUDIO_AVAILABLE=true
    AUDIO_DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$AUDIO_SOURCE")
    echo "Audio source: $AUDIO_SOURCE (${AUDIO_DURATION}s)"
fi

# Pull only new/changed screen recordings from Android device
echo "Checking for new screen recordings..."
mkdir -p "$INPUT_DIR/Screen recordings"

adb shell ls -l "\"$ANDROID_SCREEN_RECORDINGS\"" 2>/dev/null | while IFS= read -r line; do
    # Parse size and filename from adb ls -l output
    # Format: permissions links owner group SIZE DATE TIME FILENAME
    size=$(echo "$line" | awk '{print $5}')
    name=$(echo "$line" | awk '{for(i=8;i<=NF;i++) printf "%s%s", (i>8?" ":""), $i; print ""}')

    case "$name" in
        *.mp4) ;;
        *) continue ;;
    esac

    local_file="$INPUT_DIR/Screen recordings/$name"

    # Check if local file exists with same size
    if [ -f "$local_file" ]; then
        local_size=$(stat -f%z "$local_file" 2>/dev/null || stat -c%s "$local_file" 2>/dev/null)
        if [ "$local_size" = "$size" ]; then
            echo "Skipping pull: $name (same size)"
            continue
        fi
    fi

    echo "Pulling: $name"
    adb pull "$ANDROID_SCREEN_RECORDINGS/$name" "$local_file"
done

for video in "$INPUT_DIR/Screen recordings"/*.mp4; do
    [ -f "$video" ] || continue

    filename=$(basename "$video")
    output="$OUTPUT_DIR/${filename%.*}_reel.mp4"

    # Skip if output already exists
    if [ -f "$output" ]; then
        echo "Skipping: $filename (already processed)"
        continue
    fi

    # Get original duration
    duration=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$video")

    # Calculate: speed up first (duration-2) seconds to fit in 17 seconds, keep last 2 seconds normal
    speed_part=$(echo "$duration - 2" | bc -l)
    speed=$(echo "$speed_part / 17" | bc -l)
    last_start=$(echo "$duration - 2" | bc -l)

    echo "Processing: $filename (${speed_part}s sped up to 17s + 2s normal = 19s)"

    # Create temp files
    temp1=$(mktemp).mp4
    temp2=$(mktemp).mp4
    concat_list=$(mktemp).txt

    # Part 1: Speed up everything except last 2 seconds
    ffmpeg -y -i "$video" -t "$speed_part" \
        -vf "crop=in_w:in_h-$CROP_BOTTOM:0:0,setpts=PTS/$speed,scale=-2:1920,pad=1080:1920:(1080-iw)/2:0:black" \
        -an -r 30 -c:v libx264 -preset fast -crf 18 \
        "$temp1"

    # Part 2: Last 2 seconds at normal speed
    ffmpeg -y -i "$video" -ss "$last_start" \
        -vf "crop=in_w:in_h-$CROP_BOTTOM:0:0,scale=-2:1920,pad=1080:1920:(1080-iw)/2:0:black" \
        -an -r 30 -c:v libx264 -preset fast -crf 18 \
        "$temp2"

    # Concatenate video parts
    echo "file '$temp1'" > "$concat_list"
    echo "file '$temp2'" >> "$concat_list"
    temp_video=$(mktemp).mp4
    ffmpeg -y -f concat -safe 0 -i "$concat_list" -c copy "$temp_video"

    # Add audio with random start offset
    if [ "$AUDIO_AVAILABLE" = true ]; then
        # Calculate max start offset so audio covers entire video (no silence at end)
        # max_offset = audio_duration - video_duration
        max_offset=$(echo "$AUDIO_DURATION - $TARGET_DURATION" | bc -l)
        if (( $(echo "$max_offset > 0" | bc -l) )); then
            # Random offset between 0 and max_offset (ensures audio won't run out)
            random_offset=$(echo "scale=2; $RANDOM / 32767 * $max_offset" | bc -l)
            echo "Adding audio with offset: ${random_offset}s (max: ${max_offset}s)"
            ffmpeg -y -i "$temp_video" -ss "$random_offset" -i "$AUDIO_SOURCE" \
                -map 0:v -map 1:a -c:v copy -c:a aac -b:a 128k -t $TARGET_DURATION "$output"
            rm -f "$temp_video"
        else
            # Audio shorter than video - skip audio to avoid silence
            echo "Warning: Audio too short (${AUDIO_DURATION}s < ${TARGET_DURATION}s), skipping audio"
            mv "$temp_video" "$output"
        fi
    else
        mv "$temp_video" "$output"
    fi

    # Cleanup
    rm -f "$temp1" "$temp2" "$concat_list"

    echo "Saved: $output"
done

echo "Done! Processed videos in: $OUTPUT_DIR"
