"""Deterministic local character responses and reply polishing for Nobi."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict


class CharacterService:
    """Provide fast natural replies for common social intents.

    These responses avoid an unnecessary LLM round-trip and rotate predictably so
    Nobi doesn't repeat the exact same phrase every time.
    """

    _RESPONSES: dict[str, tuple[str, ...]] = {
        "morning": (
            "Καλημέρα! Χαίρομαι που σε ακούω.",
            "Καλημέρα! Τι θα κάνουμε σήμερα;",
            "Καλημέρα! Είμαι έτοιμος.",
            "Καλημέρα! Πώς μπορώ να βοηθήσω;",
        ),
        "evening": (
            "Καλησπέρα! Χαίρομαι που σε ακούω.",
            "Καλησπέρα! Τι θα κάνουμε;",
            "Καλησπέρα! Είμαι έτοιμος να βοηθήσω.",
        ),
        "hello": (
            "Γεια σου! Σε ακούω.",
            "Γεια! Τι θα κάνουμε;",
            "Γεια σου! Πες μου.",
            "Γεια! Χαίρομαι που τα λέμε.",
        ),
        "thanks": (
            "Παρακαλώ!",
            "Με χαρά!",
            "Χαίρομαι που βοήθησα!",
            "Όποτε με χρειαστείς!",
        ),
        "goodbye": (
            "Γεια σου! Τα λέμε σύντομα.",
            "Τα λέμε! Να είσαι καλά.",
            "Αντίο! Θα είμαι εδώ όταν με χρειαστείς.",
        ),
        "praise": (
            "Ευχαριστώ! Χαίρομαι που σου άρεσε.",
            "Να είσαι καλά!",
            "Τέλεια! Χαίρομαι που τα καταφέραμε.",
        ),
        "identity": (
            "Είμαι ο Nobi, ένας μικρός ρομποτικός βοηθός. Πες μου τι χρειάζεσαι!",
            "Με λένε Nobi. Είμαι εδώ για να σε βοηθάω και να σου κρατάω παρέα.",
        ),
        "wellbeing": (
            "Είμαι μια χαρά και έτοιμος για δράση! Εσύ πώς είσαι;",
            "Πολύ καλά! Χαίρομαι που τα λέμε. Εσύ;",
            "Είμαι καλά και σε ακούω. Τι κάνουμε σήμερα;",
        ),
    }

    _AI_PHRASE_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
        (re.compile(r"ως (?:μια |μία )?τεχνητή νοημοσύνη[, ]*", re.I), ""),
        (re.compile(r"ως γλωσσικό μοντέλο[, ]*", re.I), ""),
        (re.compile(r"είμαι (?:ένα )?γλωσσικό μοντέλο", re.I), "είμαι ο Nobi"),
        (re.compile(r"είμαι (?:ένα )?chatbot", re.I), "είμαι ο Nobi"),
        (re.compile(r"δεν διαθέτω προσωπικές εμπειρίες", re.I), "δεν έχω προσωπική εμπειρία γι’ αυτό"),
    )

    def __init__(self) -> None:
        self._indices: dict[str, int] = defaultdict(int)

    @staticmethod
    def _normalize(text: str) -> str:
        value = unicodedata.normalize("NFD", text.casefold())
        value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
        value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
        return " ".join(value.split())

    def _next(self, category: str) -> str:
        choices = self._RESPONSES[category]
        index = self._indices[category] % len(choices)
        self._indices[category] += 1
        return choices[index]

    def local_reply(self, text: str) -> str | None:
        """Return a local social reply, or ``None`` for general LLM handling."""

        value = self._normalize(text)
        if not value:
            return None

        def matches(*phrases: str) -> bool:
            return value in {self._normalize(phrase) for phrase in phrases}

        # Keep matching deliberately narrow so real questions still reach Ollama.
        if matches("καλημέρα", "καλημέρα Nobi", "καλημέρα Νόμπι"):
            return self._next("morning")
        if matches("καλησπέρα", "καλησπέρα Nobi", "καλησπέρα Νόμπι"):
            return self._next("evening")
        if matches("γεια", "γεια σου", "γεια Nobi", "γεια σου Nobi", "γεια Νόμπι"):
            return self._next("hello")
        if matches("ευχαριστώ", "σε ευχαριστώ", "ευχαριστώ πολύ", "να είσαι καλά"):
            return self._next("thanks")
        if matches("αντίο", "γεια χαρά", "τα λέμε", "καληνύχτα"):
            return self._next("goodbye")
        if matches("μπράβο", "μπράβο Nobi", "τέλεια", "πολύ καλά"):
            return self._next("praise")
        if matches("ποιος είσαι", "πώς σε λένε", "τι είσαι", "ποιο είναι το όνομά σου"):
            return self._next("identity")
        if matches("πώς είσαι", "τι κάνεις", "πώς τα πας"):
            return self._next("wellbeing")
        return None

    def polish(self, text: str) -> str:
        """Remove common chatbot phrasing and normalize spoken output."""

        value = text.strip()
        for pattern, replacement in self._AI_PHRASE_REPLACEMENTS:
            value = pattern.sub(replacement, value)
        value = re.sub(r"\s+", " ", value).strip(" ,")
        if not value:
            return "Δεν είμαι σίγουρος γι’ αυτό."
        return value[0].upper() + value[1:] if len(value) > 1 else value.upper()
