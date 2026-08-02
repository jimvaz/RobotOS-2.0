from brain.persona import CHARACTER_MOTTO, CHARACTER_SYSTEM_PROMPT, build_system_prompt


def test_character_prompt_is_greek_and_voice_friendly():
    assert "αποκλειστικά στα ελληνικά" in CHARACTER_SYSTEM_PROMPT
    assert "markdown" in CHARACTER_SYSTEM_PROMPT
    assert CHARACTER_MOTTO.rstrip(".") in CHARACTER_SYSTEM_PROMPT


def test_prompt_builder_appends_extra_rules():
    prompt = build_system_prompt("Μην απαντάς με περισσότερες από δύο προτάσεις.")
    assert prompt.startswith(CHARACTER_SYSTEM_PROMPT)
    assert "δύο προτάσεις" in prompt
