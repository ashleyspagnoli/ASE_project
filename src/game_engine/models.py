import uuid
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Card:
    rank: str
    suit: str

    def __repr__(self):
        return f"{self.rank} of {self.suit}"


@dataclass
class Deck:
    cards: List[Card] = field(default_factory=list)

    def shuffle(self):
        random.shuffle(self.cards)

    def draw(self) -> Optional[Card]:
        if not self.cards:
            return None
        return self.cards.pop(0)

    def add_card(self, card: Card):
        self.cards.append(card)


@dataclass
class Player:
    name: str
    deck: Deck = field(default_factory=Deck)
    hand: List[Card] = field(default_factory=list)
    score: int = 0

    def draw_card(self):
        card = self.deck.draw()
        if card:
            self.hand.append(card)
        return card

    def play_card(self, card: Card):
        if card in self.hand:
            self.hand.remove(card)
            return card
        raise ValueError(f"{self.name} does not have {card}")


@dataclass
class Game:
    player1: Player
    player2: Player
    game_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    current_round: Dict[str, Card] = field(default_factory=dict)
    turn_number: int = 0
    winner: Optional[str] = None
    turns: List[Dict] = field(default_factory=list)

    def resolve_round(self, winner_name: Optional[str]):
        self.turn_number += 1
        self.turns.append({
            "turn": self.turn_number,
            "cards": {p: str(c) for p, c in self.current_round.items()},
            "winner": winner_name
        })
        self.current_round = {}

    def is_finished(self, total_turns: int = 8) -> bool:
        return self.turn_number >= total_turns
