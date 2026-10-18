"""Shared literal examples exercise the existing server rule owner, not TTS."""
import json
from pathlib import Path
from app.experimental.voice_direction import PronunciationRule, spoken_text


def test_original_spoken_text_matches_shared_preview_examples():
    rows = json.loads(Path('frontend/src/experimental/voicePronunciation.testFixture.json').read_text())
    for row in rows:
        rules = []
        for line in row['rules'].split('\n'):
            if not line.strip():
                continue
            term, pronunciation = line.split('=', 1)
            rules.append(PronunciationRule(term=term, pronunciation=pronunciation).model_dump())
        assert spoken_text(row['text'], rules) == row['expected']
