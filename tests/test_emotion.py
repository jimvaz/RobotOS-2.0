from brain.services.emotion import EmotionService
from shared.emotions import Emotion, VOICE_STYLES, parse_emotion


def test_emotion_service_selects_friendly_for_greeting():
    service = EmotionService()
    assert service.classify("Καλημέρα", "Καλημέρα! Χαίρομαι που σε ακούω.") == Emotion.FRIENDLY


def test_emotion_service_selects_excited_for_success():
    service = EmotionService()
    assert service.classify("Το έκανες;", "Τέλεια! Το κατάφερα!") == Emotion.EXCITED


def test_emotion_service_selects_curious_for_question():
    service = EmotionService()
    assert service.classify("Δεν κατάλαβα", "Μπορείς να το πεις αλλιώς;") == Emotion.CURIOUS


def test_unknown_emotion_falls_back_to_neutral():
    assert parse_emotion("unknown") == Emotion.NEUTRAL
    assert VOICE_STYLES[Emotion.NEUTRAL].exaggeration > 0
