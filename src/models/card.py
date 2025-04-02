from dataclasses import dataclass

@dataclass
class Card:
    rank: str
    suit: str
    confidence: float