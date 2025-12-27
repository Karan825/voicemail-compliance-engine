import numpy as np

class VAD:
    def __init__(
        self,
        energy_threshold=2.0, # So this tells us that how much louder a frae need to be to count as a speech
        smoothing=0.01 # This controls how fast the noise floor adapts.
    ):
        """
        energy_threshold:
            How much louder than background a frame must be to be speech

        smoothing:
            How fast the noise floor adapts
        """
        self.energy_threshold = energy_threshold
        self.smoothing = smoothing
        self.noise_floor = None

    def is_speech(self,frame):
        """
        Returns True if frame contains speech, else False
        """
        # 1. Compute short-time energy
        energy = np.mean(frame**2)
        # 2. Initialize noise floor
        if self.noise_floor is None:
            self.noise_floor = energy
            return False
        # 3. Update noise floor (slowly) -- Track background slowly
        self.noise_floor = (
                self.smoothing * energy +
                (1 - self.smoothing) * self.noise_floor
        )

        # 4. Compare energy to noise floor
        ratio = energy/(self.noise_floor+1e-9)

        return ratio > self.energy_threshold