from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import soundfile as sf
import time
import os

app = FastAPI()

FRAME_DURATION = 0.02  # 20 ms

AUDIO_FILES = {
    "vm1": "Audio/vm1_output.wav",
    "vm2": "Audio/vm2_output.wav",
    "vm3": "Audio/vm3_output.wav",
    "vm4": "Audio/vm4_output.wav",
    "vm5": "Audio/vm5_output.wav",
    "vm6": "Audio/vm6_output.wav",
    "vm7": "Audio/vm7_output.wav",
}


@app.get("/audio/stream")
def stream_audio(file: str):
    if file not in AUDIO_FILES:
        raise HTTPException(status_code=404, detail="Invalid audio file")

    path = AUDIO_FILES[file]

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")

    def audio_generator():
        audio, sr = sf.read(path) # Returns the audio file in numpy format and sample rate = 8kHz

        if audio.ndim > 1:
            audio = audio.mean(axis=1) # coverting to mono from stero

        frame_size = int(sr * FRAME_DURATION) # (8000*20ms) = 160 samples/frame -> contains 20ms info
        start_time = time.time()

        for i in range(len(audio) // frame_size):
            frame = audio[i * frame_size:(i + 1) * frame_size]

            yield (frame * 32767).astype("int16").tobytes() # since amplitude are in normalized form i convert it to int16 for transmission

            expected_time = start_time + i * FRAME_DURATION
            sleep_time = expected_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
    #streamingResponse will keep
    return StreamingResponse(
        audio_generator(),
        media_type="audio/L16"
    )
