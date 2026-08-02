"""Lightweight deterministic emotion selection for RobotOS speech."""

from __future__ import annotations

import re

from shared.emotions import Emotion


class EmotionService:
    """Choose a speaking style without adding another LLM request."""

    _greetings = ("γεια", "καλημέρα", "καλησπέρα", "καλό απόγευμα", "χαίρομαι")
    _questions = (";", "?", "μπορείς", "ποιο", "ποια", "ποιος", "τι εννοείς")
    _success = ("τέλεια", "το κατάφερα", "το βρήκα", "έγινε", "ολοκληρώθηκε")
    _funny = ("χαχα", "αστείο", "πλάκα", "γελά")
    _thinking = ("χμμ", "ας το δούμε", "μισό λεπτό", "δεν είμαι σίγουρος", "νομίζω")

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.casefold().strip())

    def classify(self, user_text: str, assistant_text: str) -> Emotion:
        user = self._normalize(user_text)
        assistant = self._normalize(assistant_text)
        combined = f"{user} {assistant}"

        if any(token in combined for token in self._funny):
            return Emotion.FUNNY
        if any(token in assistant for token in self._success):
            return Emotion.EXCITED
        if any(token in assistant for token in self._thinking):
            return Emotion.THINKING
        if any(token in assistant for token in self._greetings):
            return Emotion.FRIENDLY
        if assistant.endswith((";", "?")) or any(token in assistant for token in self._questions):
            return Emotion.CURIOUS
        return Emotion.NEUTRAL
