# src/models/hand_history.py
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from src.models.card import Card

@dataclass
class Action:
    street: str
    player: str
    action_type: str
    amount: float = None
    reasoning: str = None

@dataclass
class HandHistory:
    hand_id: int
    hero_cards: List[Card]
    community_cards: List[Card] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)
    current_street: str = "Preflop"
    preflop_pot_type: str = "unknown"  # Store the pre-flop scenario
    pot_type_description: str = ""     # Add description of pot type
    
    # Track last action for each player on each street to prevent duplicates and impossible sequences
    _last_actions: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    def add_action(self, player: str, action_type: str, amount: float = None, street: str = None, reasoning: str = None):
        """Add an action to the history with validation"""
        # Use provided street or current_street if not provided
        action_street = street if street is not None else self.current_street
        
        # Skip recording actions during preflop if that's still the policy
        if action_street == "Preflop" and street is None:
            return
        
        # Initialize tracking for this street if needed
        if action_street not in self._last_actions:
            self._last_actions[action_street] = {}
        
        # Check for invalid action sequences
        last_action = self._last_actions.get(action_street, {}).get(player)
        
        # Prevent impossible sequences (e.g., bet then check on same street)
        if last_action:
            # Player can't check after betting or raising
            if action_type == "CHECK" and last_action in ["BET", "RAISE"]:
                print(f"ERROR: Cannot add {action_type} after {last_action} for {player} on {action_street}")
                return
                
            # Player can't bet after betting (should be a raise)
            if action_type == "BET" and last_action == "BET":
                print(f"ERROR: Cannot add another {action_type} for {player} on {action_street}")
                return
                
            # Player can't fold/call/raise without an opponent bet
            if action_type in ["FOLD", "CALL", "RAISE"] and last_action not in ["BET", "RAISE"]:
                # Special case: don't prevent explicitly recorded calls from later inference
                if not (action_type == "CALL" and reasoning is None):
                    print(f"ERROR: Cannot {action_type} without opponent bet for {player} on {action_street}")
                    return
        
        # Check for duplicates (exact same action on same street by same player)
        for existing_action in self.actions:
            if (existing_action.player == player and 
                existing_action.action_type == action_type and 
                existing_action.street == action_street):
                # Allow duplicates if they have different amounts (e.g., raises)
                if action_type in ["BET", "RAISE", "CALL"] and existing_action.amount != amount:
                    continue
                    
                print(f"Skipping duplicate action: {player} {action_type} on {action_street}")
                return
        
        # Update the last action for this player on this street
        self._last_actions[action_street][player] = action_type
        
        # Create and add the action
        action = Action(
            street=action_street,
            player=player,
            action_type=action_type,
            amount=amount,
            reasoning=reasoning
        )
        self.actions.append(action)
        print(f"Added action: {player} {action_type}" + (f" ${amount:.2f}" if amount else "") + f" on {action_street}")
    
    def set_preflop_pot_type(self, pot_type: str, description: str = ""):
        """Set the visually detected preflop pot type"""
        self.preflop_pot_type = pot_type
        self.pot_type_description = description
    
    def update_community_cards(self, cards: List[Card]):
        """Update community cards and determine current street"""
        self.community_cards = cards
        self.current_street = self._determine_street()
    
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
    
    def infer_missing_actions(self, current_state, previous_state=None):
        """
        Comprehensively infer missing actions based on state changes
        """
        if not previous_state:
            # First state of a new street - check if BB (VILLAIN ONLY) needs to act first
            if current_state['street'] != "Preflop":
                positions = current_state.get('positions', {})
                bb_player = positions.get('BB', '').lower()
                
                # Only auto-add check for villain BB if they have no bet
                if bb_player == "villain" and current_state['bets'][bb_player] == 0:
                    # Check if there are already actions for this street
                    street_actions = [a for a in self.actions if a.street == current_state['street']]
                    if not street_actions:
                        self.add_action(
                            player=bb_player,
                            action_type="CHECK",
                            street=current_state['street']
                        )
            return
        
        prev_street = previous_state['street']
        current_street = current_state['street']
        
        # Check for street change - need to infer ending actions of previous street
        if current_street != prev_street:
            # Find the last betting action on the previous street
            prev_street_actions = [a for a in self.actions if a.street == prev_street]
            
            # Sort actions by their order in the master action list
            prev_street_actions.sort(key=lambda a: self.actions.index(a))
            
            # If previous street had actions
            if prev_street_actions:
                # Get the last action on the previous street
                last_action = prev_street_actions[-1]
                
                # If the last action was a bet or raise, the opponent must have called
                if last_action.action_type in ["BET", "RAISE"]:
                    # Determine who needs to call
                    caller = "villain" if last_action.player == "hero" else "hero"
                    
                    # Check if caller already acted after the bet/raise
                    last_action_index = self.actions.index(last_action)
                    caller_already_acted = False
                    
                    for i in range(last_action_index + 1, len(self.actions)):
                        if (self.actions[i].player == caller and 
                            self.actions[i].street == prev_street):
                            caller_already_acted = True
                            break
                    
                    # Only add the call if it hasn't been recorded yet
                    if not caller_already_acted:
                        # Check if the pot size makes sense for a call
                        # If villain's bet is still there on next street, they didn't fold
                        if (current_state['bets'][caller] == 0 and 
                            'pot_size' in current_state and 
                            'pot_size' in previous_state and
                            current_state['pot_size'] > previous_state['pot_size']):
                            
                            self.add_action(
                                player=caller,
                                action_type="CALL",
                                amount=last_action.amount,
                                street=prev_street
                            )
                    
                # If no actions or last action wasn't a bet/raise, infer checks if needed
                else:
                    positions = previous_state.get('positions', {})
                    bb_player = positions.get('BB', '').lower()
                    sb_player = positions.get('SB', '').lower()
                    
                    # Check if BB needs to check
                    if bb_player:
                        bb_acted = any(a.player == bb_player and a.street == prev_street for a in prev_street_actions)
                        # Only add check if BB hasn't acted AND has no current bet
                        if not bb_acted and previous_state['bets'][bb_player] == 0:
                            self.add_action(
                                player=bb_player,
                                action_type="CHECK",
                                street=prev_street
                            )
                    
                    # Check if SB needs to check
                    if sb_player:
                        sb_acted = any(a.player == sb_player and a.street == prev_street for a in prev_street_actions)
                        # Only add check if SB hasn't acted AND has no current bet
                        if not sb_acted and previous_state['bets'][sb_player] == 0:
                            self.add_action(
                                player=sb_player,
                                action_type="CHECK",
                                street=prev_street
                            )
            else:
                # No actions recorded for the previous street - infer checks for both players
                positions = previous_state.get('positions', {})
                bb_player = positions.get('BB', '').lower()
                sb_player = positions.get('SB', '').lower()
                
                # Only infer checks if the bets are 0 (no one bet)
                if bb_player and previous_state['bets'][bb_player] == 0:
                    self.add_action(
                        player=bb_player,
                        action_type="CHECK",
                        street=prev_street
                    )
                
                if sb_player and previous_state['bets'][sb_player] == 0:
                    self.add_action(
                        player=sb_player,
                        action_type="CHECK",
                        street=prev_street
                    )
    
    def format_history(self) -> str:
        """Format the hand history into a readable string with pot sizes"""
        history = []
        
        # Add preflop scenario information first
        if self.preflop_pot_type != "unknown":
            history.append(f"Pot type: {self.preflop_pot_type} - Preflop action: {self.pot_type_description}")
        
        # Track running pot size based on preflop pot type
        running_pot = 3.0  # Default starting pot (SB 0.5 + BB 1 + ante if any)
        if self.preflop_pot_type == "2_bet_pot":
            running_pot = 5.0  # SB raised to 2.5, BB called = 5.0
        elif self.preflop_pot_type == "3_bet_pot":
            running_pot = 20.0  # SB opens 2.5, BB 3-bets to 10, SB calls = 20.0
        elif self.preflop_pot_type == "4_bet_pot":
            running_pot = 50.0  # SB opens 2.5, BB 3-bets to 10, SB 4-bets to 25, BB calls = 50.0
        
        # Process actions by street
        for street in ["Flop", "Turn", "River"]:
            street_actions = [a for a in self.actions if a.street == street]
            if not street_actions:
                continue
            
            # Sort actions chronologically by their index in the main action list
            street_actions.sort(key=lambda a: self.actions.index(a))
            
            history.append(f"\n## {street}: (Pot: ${running_pot:.2f})")
            
            for action in street_actions:
                action_text = f"- {action.player} {action.action_type}"
                
                # Update running pot based on action
                if action.action_type in ["BET", "RAISE"]:
                    running_pot += action.amount if action.amount else 0
                elif action.action_type == "CALL":
                    running_pot += action.amount if action.amount else 0
                    
                if action.amount:
                    action_text += f" ${action.amount:.2f}"
                    
                # Add updated pot size after bet/raise/call
                if action.action_type in ["BET", "RAISE", "CALL"]:
                    action_text += f" (Pot: ${running_pot:.2f})"
                
                # Add reasoning if available (only for hero's actions)
                if action.reasoning and action.player == "hero":
                    action_text += f"\n  Reasoning: {action.reasoning}"
                    
                history.append(action_text)
                    
        return "\n".join(history)