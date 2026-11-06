from pathlib import Path

from apps.pptx.parser import Deck

SAMPLE = Path(__file__).resolve().parents[3] / "samples" / "pptx" / "sample.pptx"


def test_sample_deck_has_slides():
    deck = Deck(str(SAMPLE))
    assert len(deck) > 0
    assert deck.slide(0) is not None
