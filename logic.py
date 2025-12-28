import httpx
import numpy as np
import sys
import time

from beep import BeepDetector
from vad import VAD

# =========================
# STREAM CONFIG
# =========================
print('Choose file number to stream:')
n = int(input())
STREAM_URL = f"http://127.0.0.1:8000/audio/stream?file=vm{n}"

SAMPLE_RATE = 8000
FRAME_DURATION = 0.02  # 20 ms
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION)

SILENCE_THRESHOLD_SEC = 2
BEEP_OFFSET = 0.02
SILENCE_OFFSET = 0.1


def main():
    # -------------------------
    # Initialize detectors
    # -------------------------
    beep_detector = BeepDetector(SAMPLE_RATE)
    vad = VAD()

    # -------------------------
    # Streaming state
    # -------------------------
    audio_buffer = b""
    total_samples_seen = 0

    silence_duration = 0.0
    heard_speech = False
    decision_made = False

    last_printed_second = -1

    print("\n [CALL CONNECTED]")
    print(" Listening to voicemail...\n")

    # =========================
    # STREAM AUDIO
    # =========================
    with httpx.stream("GET", STREAM_URL) as r:
        for chunk in r.iter_bytes():
            audio_buffer += chunk

            # Process complete frames only
            while len(audio_buffer) >= FRAME_SAMPLES * 2:
                frame_bytes = audio_buffer[: FRAME_SAMPLES * 2]
                audio_buffer = audio_buffer[FRAME_SAMPLES * 2 :]

                # -------------------------
                # Bytes → PCM float frame
                # -------------------------
                frame = (
                    np.frombuffer(frame_bytes, dtype=np.int16)
                    .astype(np.float32) / 32768.0
                )

                # -------------------------
                # Sample-accurate timestamp
                # -------------------------
                timestamp = total_samples_seen / SAMPLE_RATE
                total_samples_seen += len(frame)

                # -------------------------
                # UI: progress indicator
                # -------------------------
                current_sec = int(timestamp)
                if current_sec != last_printed_second:
                    last_printed_second = current_sec
                    rms = np.sqrt(np.mean(frame**2))
                    sys.stdout.write(
                        f"\r⏱  {timestamp:5.1f}s | level={rms:.4f} | listening..."
                    )
                    sys.stdout.flush()

                if decision_made:
                    continue

                # =========================
                # Beep detection
                # =========================
                beep_time = beep_detector.process(frame, timestamp)
                if beep_time is not None:
                    print(
                        "\n\n [COMPLIANCE DECISION]"
                        "\nReason : Beep detected"
                        f"\nAction : Start voicemail at {beep_time + BEEP_OFFSET:.2f}s\n"
                    )
                    decision_made = True
                    return

                # =========================
                #  Voice Activity Detection
                # =========================
                if vad.is_speech(frame):
                    heard_speech = True
                    silence_duration = 0.0
                else:
                    if heard_speech:
                        silence_duration += FRAME_DURATION

                # =========================
                #  Silence-based fallback
                # =========================
                if heard_speech and silence_duration >= SILENCE_THRESHOLD_SEC:
                    start_time = timestamp - silence_duration
                    print(
                        "\n\n [COMPLIANCE DECISION]"
                        "\nReason : Sustained silence (no beep)"
                        f"\nAction : Start voicemail at {start_time + SILENCE_OFFSET:.2f}s\n"
                    )
                    decision_made = True
                    return


if __name__ == "__main__":
    main()

