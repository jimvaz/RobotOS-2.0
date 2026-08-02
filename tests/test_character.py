from brain.services.character import CharacterService


def test_local_greeting_rotates_without_llm():
    service = CharacterService()
    first = service.local_reply("Καλημέρα")
    second = service.local_reply("Καλημέρα")
    assert first
    assert second
    assert first != second


def test_general_question_is_not_intercepted():
    service = CharacterService()
    assert service.local_reply("Ποια είναι η πρωτεύουσα της Ελλάδας;") is None


def test_identity_is_nobi():
    service = CharacterService()
    reply = service.local_reply("Ποιος είσαι;")
    assert reply is not None
    assert "Nobi" in reply


def test_polish_removes_chatbot_phrasing():
    service = CharacterService()
    result = service.polish("Ως γλωσσικό μοντέλο, δεν διαθέτω προσωπικές εμπειρίες.")
    assert "γλωσσικό μοντέλο" not in result.casefold()
    assert "προσωπική εμπειρία" in result.casefold()
