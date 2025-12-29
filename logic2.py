import os

import httpx
import numpy as np
import sys
import threading
from deepgram import DeepgramClient
from deepgram.core.events import EventType
from deepgram.extensions.types.sockets import ListenV1SocketClientResponse

from llm import GreetingLLM
from beep import BeepDetector
from vad import VAD
from load_dotenv import load_dotenv

load_dotenv()

# =========================
# STREAM CONFIG
# =========================
print("Choose file number to stream (1–7):")
n = int(input())
STREAM_URL = f"http://127.0.0.1:8000/audio/stream?file=vm{n}"

SAMPLE_RATE = 8000
FRAME_DURATION = 0.02
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION)

SILENCE_THRESHOLD_SEC = 2
BEEP_OFFSET = 0.02
SILENCE_OFFSET = 0.1


def main():
    beep_detector = BeepDetector(SAMPLE_RATE)
    vad = VAD()
    llm = GreetingLLM()

    deepgram = DeepgramClient(api_key=os.getenv("DEEPGRAM_API_KEY"))

    latest_transcript = ""
    transcript_lock = threading.Lock()

    # =========================
    # OPEN DEEPGRAM SOCKET
    # =========================
    with deepgram.listen.v1.connect(
        model="nova-3",
        encoding="linear16",
        sample_rate=8000,
        channels=1,
        punctuate=True,
        interim_results=True,
    ) as connection:

        # -------------------------
        # Transcript handler
        # -------------------------
        def on_message(message: ListenV1SocketClientResponse):
            nonlocal latest_transcript

            if hasattr(message, "channel") and message.channel.alternatives:
                text = message.channel.alternatives[0].transcript
                if text:
                    with transcript_lock:
                        latest_transcript = text
                    print("\n[DG]", text)

        connection.on(EventType.MESSAGE, on_message)
        connection.on(EventType.OPEN, lambda _: print("[DG] Connection opened"))
        connection.on(EventType.CLOSE, lambda _: print("[DG] Connection closed"))
        connection.on(EventType.ERROR, lambda e: print(f"[DG ERROR] {e}"))

        # Start listening thread
        listen_thread = threading.Thread(
            target=connection.start_listening, daemon=True
        )
        listen_thread.start()

        # =========================
        # STREAM AUDIO FROM FASTAPI
        # =========================
        audio_buffer = b""
        total_samples_seen = 0
        silence_duration = 0.0
        heard_speech = False

        print("\n[CALL CONNECTED]")
        print("Listening to voicemail...\n")

        with httpx.stream("GET", STREAM_URL) as r:
            for chunk in r.iter_bytes():
                audio_buffer += chunk

                while len(audio_buffer) >= FRAME_SAMPLES * 2:
                    frame_bytes = audio_buffer[: FRAME_SAMPLES * 2]
                    audio_buffer = audio_buffer[FRAME_SAMPLES * 2 :]

                    # -------------------------
                    # SEND AUDIO TO DEEPGRAM
                    # -------------------------
                    connection.send_media(frame_bytes)

                    # -------------------------
                    # DSP FRAME
                    # -------------------------
                    frame = (
                        np.frombuffer(frame_bytes, dtype=np.int16)
                        .astype(np.float32) / 32768.0
                    )

                    timestamp = total_samples_seen / SAMPLE_RATE
                    total_samples_seen += len(frame)

                    # =========================
                    # Beep detection
                    # =========================
                    beep_time = beep_detector.process(frame, timestamp)
                    if beep_time is not None:
                        print(
                            "\n\n[COMPLIANCE DECISION]"
                            "\nReason : Beep detected"
                            f"\nAction : Start voicemail NOW "
                            f"(greeting ended at {beep_time + BEEP_OFFSET:.2f}s)\n"
                        )
                        connection.finish()
                        return

                    # =========================
                    # VAD
                    # =========================
                    if vad.is_speech(frame):
                        heard_speech = True
                        silence_duration = 0.0
                    else:
                        if heard_speech:
                            silence_duration += FRAME_DURATION

                    # =========================
                    # Silence + LLM fallback
                    # =========================
                    with transcript_lock:
                        current_transcript = latest_transcript

                    ans = llm.greeting_finished(current_transcript)

                    if (
                        heard_speech
                        and silence_duration >= SILENCE_THRESHOLD_SEC
                        and ans == "YES"
                    ):
                        greeting_end = timestamp - silence_duration
                        print(
                            "\n\n[COMPLIANCE DECISION]"
                            "\nReason : Sustained silence + LLM confirmation"
                            f"\nAction : Start voicemail NOW "
                            f"(greeting ended at {greeting_end + SILENCE_OFFSET:.2f}s)\n"
                        )
                        connection.finish()
                        return


if __name__ == "__main__":
    main()
