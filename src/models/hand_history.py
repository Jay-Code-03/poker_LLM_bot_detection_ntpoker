# src/models/hand_history.py
from typing import List, Dict
from dataclasses import dataclass, field
from src.models.card import Card

@dataclass
class Action:
    street: str
    player: str
    action_type: str
    amount: float = None

@dataclass
class HandHistory:
    hand_id: int
    hero_cards: List[Card]
    community_cards: List[Card] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    current_street: str = "Preflop"
    preflop_scenario: str = "unknown"  # Store the pre-flop scenario
    preflop_pot_type: str = "unknown"  # Add new field for visually detected pot type
    pot_type_description: str = ""     # Add description of pot type
    
    def add_action(self, player: str, action_type: str, amount: float = None, street: str = None):
        """Add an action to the history"""
        # Use provided street or current_street if not provided
        action_street = street if street is not None else self.current_street
        
        # Skip recording actions during preflop if that's still the policy
        if action_street == "Preflop" and street is None:
            return
            
        action = Action(
            street=action_street,
            player=player,
            action_type=action_type,
            amount=amount
        )
        self.actions.append(action)

    def set_preflop_pot_type(self, pot_type: str, description: str = ""):
        """Set the visually detected preflop pot type"""
        self.preflop_pot_type = pot_type
        self.pot_type_description = description
    
    def update_community_cards(self, cards: List[Card]):
        """Update community cards and determine current street"""
        self.community_cards = cards
        self.current_street = self._determine_street()
    
    def set_preflop_scenario(self, scenario: str):
        """Set the identified pre-flop scenario"""
        self.preflop_scenario = scenario
    
    def _determine_street(self) -> str:
        """Determine current street based on number of community cards"""
        num_cards = len(self.community_cards)
        if num_cards == 0:
            return "Preflop"
        elif num_cards == 3:
            return "Flop"
        elif num_cards == 4:
            return "Turn"
        elif num_cards == 5:
            return "River"
        return "Unknown"
    
    def format_history(self) -> str:
        """Format the hand history into a readable string"""
        history = []
        
        # Add preflop scenario information first
        #history.append(f"Preflop scenario: {self.preflop_scenario}")

        if self.preflop_pot_type != "unknown":
            history.append(f"Pot type: {self.preflop_pot_type} - Preflop action: {self.pot_type_description}")
        
        # Only include post-flop actions
        for street in ["Flop", "Turn", "River"]:
            street_actions = [a for a in self.actions if a.street == street]
            if not street_actions:
                continue
                
            history.append(f"\n## {street}:")
            for action in street_actions:
                if action.amount:
                    history.append(f"- {action.player} {action.action_type} {action.amount:.2f}")
                else:
                    history.append(f"- {action.player} {action.action_type}")
                
        return "\n".join(history)