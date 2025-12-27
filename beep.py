import numpy as np

class BeepDetector:
    def __init__(
        self,
        sample_rate,
        min_frames=5,
        max_frames=150,         # ~300 ms
        band_ratio_thresh=0.45,
        peak_dom_thresh=10.0,
        energy_spike_mult=2.0
    ):
        self.sample_rate = sample_rate

        self.min_frames = min_frames
        self.max_frames = max_frames
        self.band_ratio_thresh = band_ratio_thresh
        self.peak_dom_thresh = peak_dom_thresh
        self.energy_spike_mult = energy_spike_mult

        self.consecutive = 0
        self.beep_start = None
        self.detected = False

        self.energy_history = []

    def process(self, frame, timestamp):
        if self.detected:
            return None

        # ---- Windowing ---h-
        frame = frame * np.hanning(len(frame))

        # ---- FFT ----
        spectrum = np.fft.rfft(frame)
        power = np.abs(spectrum) ** 2
        freqs = np.fft.rfftfreq(len(frame), d=1.0 / self.sample_rate)

        total_energy = np.sum(power)
        if total_energy <= 1e-10:
            self._reset()
            return None

        # ---- Beep band (critical) ----
        band_mask = (freqs >= 700) & (freqs <= 2000)
        band_energy = np.sum(power[band_mask])

        band_ratio = band_energy / total_energy

        # ---- Peak dominance inside band ----
        band_power = power[band_mask]
        if len(band_power) == 0:
            self._reset()
            return None

        peak_power = np.max(band_power)
        mean_band_power = np.mean(band_power) + 1e-10
        peak_dominance = peak_power / mean_band_power

        # ---- Energy spike check ----
        self.energy_history.append(total_energy)
        if len(self.energy_history) > 10:
            self.energy_history.pop(0)

        energy_spike = False
        if len(self.energy_history) >= 5:
            prev_mean = np.mean(self.energy_history[:-1])
            energy_spike = total_energy > prev_mean * self.energy_spike_mult

        # ---- Beep decision ----
        is_beep = (
            band_ratio > self.band_ratio_thresh and
            peak_dominance > self.peak_dom_thresh and
            energy_spike
        )

        # ---- Duration logic ----
        if is_beep:
            if self.consecutive == 0:
                self.beep_start = timestamp
            self.consecutive += 1

            if self.consecutive > self.max_frames:
                self._reset()
                return None
        else:
            self._reset()

        if self.consecutive >= self.min_frames:
            self.detected = True
            return self.beep_start

        return None

    def _reset(self):
        self.consecutive = 0
        self.beep_start = None
