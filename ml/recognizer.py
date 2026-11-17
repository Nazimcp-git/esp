"""recognizer.py - Accept/Lock Recognition State Machine.

States:
1. ARMED: Waiting for candidate gesture.
2. CANDIDATE: Consecutive identical high-confidence predictions accumulating.
3. LOCKED: Phrase just triggered and spoken; locked until the hand returns to neutral.

Prevents repeated speech triggers on held gestures and suppresses transitions.
"""

import numpy as np

class Recognizer:
    def __init__(self, classes, threshold=0.70, stable=4, neutral_needed=3):
        self.classes = classes
        self.threshold = threshold
        self.stable = stable
        self.neutral_needed = neutral_needed
        self.cand = None
        self.count = 0
        self.locked = False
        self.neutral = 0

    def update(self, proba, moving):
        """Call once per window (10 per second).
        
        Args:
            proba: Array of class probabilities.
            moving: Boolean, True if hand motion exceeds threshold.
            
        Returns:
            Class index integer if a phrase fires, else None.
        """
        k = int(np.argmax(proba))
        p = float(proba[k])
        is_neutral = self.classes[k] == "neutral"

        # 1. Motion suppression: Hand is transitioning, discard candidates
        if moving:
            self.cand, self.count, self.neutral = None, 0, 0
            return None

        # 2. Locked state: Phrase was recently fired; wait for hand to return to neutral
        if self.locked:
            self.neutral = self.neutral + 1 if (is_neutral and p >= 0.60) else 0
            if self.neutral >= self.neutral_needed:
                self.locked, self.neutral, self.cand, self.count = False, 0, None, 0
            return None

        # 3. Neutral or low-confidence: Hand at rest or ambiguous pose
        if is_neutral or p < self.threshold:
            self.cand, self.count = None, 0
            return None

        # 4. Candidate accumulation
        if k == self.cand:
            self.count += 1
        else:
            self.cand, self.count = k, 1

        # 5. Stability threshold reached: Fire phrase and lock
        if self.count >= self.stable:
            self.locked, self.neutral, self.cand, self.count = True, 0, None, 0
            return k

        return None

