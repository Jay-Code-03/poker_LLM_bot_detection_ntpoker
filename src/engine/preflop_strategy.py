# src/engine/preflop_strategy.py
from typing import Dict, Tuple, List, Optional
import random
from src.models.card import Card

class PreFlopStrategy:
    def __init__(self, ranges_dir="ranges"):

        """Initialize with range files."""
        self.ranges_dir = ranges_dir

        self.sb_open_range = self.load_range_from_file("sb_open")

        self.bb_call_range = self.load_range_from_file("bb_call")
        self.bb_3bet_range = self.load_range_from_file("bb_3bet")

        self.sb_4bet_range = self.load_range_from_file("sb_4bet")
        self.sb_call_vs_3bet_range = self.load_range_from_file("sb_call_vs_3bet")

        self.bb_5bet_range = self.load_range_from_file("bb_5bet")
        self.bb_call_vs_4bet_range = self.load_range_from_file("bb_call_vs_4bet")



    def load_range_from_file(self, filename: str) -> Dict[str, float]:
        """Load a range from a file."""
        try:
            with open(f"ranges/{filename}.txt", 'r') as f:
                range_str = f.read().strip()
            return self._parse_range(range_str)
        except Exception as e:
            print(f"Error loading range from file {filename}: {e}")
            return {}
        
    def _parse_range(self, range_str: str) -> Dict[str, float]:
        """Parse a range string into a dictionary of hands and frequencies."""
        range_dict = {}
        parts = range_str.strip().split(',')
        
        for part in parts:
            if ':' in part:
                hand, freq = part.split(':')
                range_dict[hand] = float(freq)
            else:
                range_dict[part] = 1.0
                
        return range_dict
    
    def _normalize_hand(self, cards: List[Card]) -> str:
        """Convert a list of Cards to a standard hand notation."""
        if len(cards) != 2:
            return "Invalid hand"
            
        # Sort cards by rank
        rank_order = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, 
                    '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
        sorted_cards = sorted(cards, key=lambda card: rank_order[card.rank], reverse=True)
        
        rank1, suit1 = sorted_cards[0].rank, sorted_cards[0].suit
        rank2, suit2 = sorted_cards[1].rank, sorted_cards[1].suit
        
        # Check if suited or offsuit
        if suit1 == suit2:
            if rank1 == rank2:  # Pair
                return f"{rank1}{rank2}"
            else:
                return f"{rank1}{rank2}s"
        else:  # Offsuit
            if rank1 == rank2:  # Pair
                return f"{rank1}{rank2}"
            else:
                return f"{rank1}{rank2}o"
            
    def is_in_range(self, cards: List[Card], range_dict: Dict[str, float]) -> Tuple[bool, float]:
        """Check if a hand is in the specified range and return its frequency."""
        hand = self._normalize_hand(cards)
        
        # Handle special case for pairs
        if len(hand) >= 2 and hand[0] == hand[1]:
            hand = hand[:2]
            
        # First try exact match
        if hand in range_dict:
            return True, range_dict[hand]
            
        # If not found, try without the 's' or 'o' suffix
        if hand.endswith('s') and hand[:-1] in range_dict:
            return True, range_dict[hand[:-1]]
            
        if hand.endswith('o') and hand[:-1] in range_dict:
            return True, range_dict[hand[:-1]]
            
        return False, 0.0
        
    def should_play(self, cards: List[Card], range_dict: Dict[str, float]) -> bool:
        """Determine if a hand should be played based on the range and frequencies."""
        in_range, freq = self.is_in_range(cards, range_dict)
        
        if not in_range:
            return False
            
        # If frequency is 1, always play
        if freq == 1.0:
            return True
            
        # Otherwise, play with probability equal to frequency
        return random.random() < freq
    
    def determine_situation(self, table_state: Dict) -> str:
        """Determine the poker situation (SB open, BB defense, etc.)."""
        # For now, we only handle SB open
        if table_state['street'] != "Preflop":
            return "not_preflop"
            
        # Check positions
        positions = table_state['positions']
        hero_bet = table_state['bets']['hero']
        villain_bet = table_state['bets']['villain']
        
        # Check if hero is SB and villain hasn't acted
        if positions.get('SB') == 'hero' and table_state['bets']['villain'] == 1: # Villain put in 1BB
            return "sb_open"
        
        # Case 2: Hero is BB facing SB raise
        if positions.get('BB') == 'hero' and villain_bet > 0:
            # Check if this is first action or not
            if hero_bet == 1:  # No prior betting from BB
                return "bb_defense"
                
        # Case 3: Hero is SB facing BB 3-bet
        if positions.get('SB') == 'hero' and villain_bet > hero_bet and hero_bet > 0.5:
            return "sb_vs_3bet"
            
        return "unknown"

    def get_action(self, table_state: Dict) -> Dict:
        """Determine the action to take based on the current state."""
        # If not our turn, do nothing
        if not table_state['is_hero_turn']:
            return {"action": "WAIT", "amount": None, "reasoning": "Not our turn"}
            
        # Determine the situation
        situation = self.determine_situation(table_state)
        
        print(f"Current situation: {situation}")
        
        if situation == "sb_open":
            # Use existing SB open logic
            return self._handle_sb_open(table_state)
        elif situation == "bb_defense":
            return self._handle_bb_defense(table_state)
        elif situation == "sb_vs_3bet":
            return self._handle_sb_vs_3bet(table_state)
        else:
            return {"action": "FOLD", "amount": None, 
                    "reasoning": f"Unknown situation: {situation}, defaulting to fold"}
        
    def _choose_action_in_range(self, table_state: Dict) -> Dict:
        """Choose action for a hand in the range."""
        actions = table_state['available_actions']
        
        # If we can raise/bet, do so
        if actions['R']:
            raise_options = actions['R']
            # Choose the minimum raise option
            min_raise = min(raise_options, key=lambda x: x['value'])
            return {"action": "RAISE", "amount": min_raise['value'], 
                    "position": min_raise['position'], 
                    "reasoning": "Hand in SB open range, raising minimum"}
            
        elif actions['B']:
            bet_options = actions['B']
            # Choose the minimum bet option
            min_bet = min(bet_options, key=lambda x: x['value'])
            return {"action": "BET", "amount": min_bet['value'], 
                    "position": min_bet['position'],
                    "reasoning": "Hand in SB open range, betting minimum"}
            
        # If we can check, do so
        elif actions['CHECK']['available']:
            return {"action": "CHECK", "amount": None, 
                    "position": actions['CHECK']['position'],
                    "reasoning": "Hand in SB open range, checking"}
            
        # If we can only fold, fold
        else:
            return {"action": "FOLD", "amount": None, 
                    "position": actions['FOLD']['position'],
                    "reasoning": "Hand in SB open range, but can only fold"}
                    
    def _choose_action_not_in_range(self, table_state: Dict) -> Dict:
        """Choose action for a hand not in the range."""
        actions = table_state['available_actions']
        
        # If we can check, do so (free play)
        if actions['CHECK']['available']:
            return {"action": "CHECK", "amount": None, 
                    "position": actions['CHECK']['position'],
                    "reasoning": "Hand not in SB open range, checking"}
        
        # Otherwise fold
        return {"action": "FOLD", "amount": None, 
                "position": actions['FOLD']['position'],
                "reasoning": "Hand not in SB open range, folding"}
    
    def _handle_sb_open(self, table_state: Dict) -> Dict:
        """Handle SB open decision."""
        hero_cards = table_state['hero_cards']
        
        # Check if our hand is in the range
        if self.should_play(hero_cards, self.sb_open_range):
            return self._choose_action_in_range(table_state)
        else:
            return self._choose_action_not_in_range(table_state)
    

    def _handle_bb_defense(self, table_state: Dict) -> Dict:
        """Handle BB defense against SB open."""
        hero_cards = table_state['hero_cards']
        actions = table_state['available_actions']
        
        # Check if hand is in 3-bet range
        if self.is_in_range(hero_cards, self.bb_3bet_range)[0]:
            # If we can raise, do so
            if actions['R']:
                raise_options = actions['R']
                # Choose the minimum raise option
                min_raise = min(raise_options, key=lambda x: x['value'])
                return {"action": "RAISE", "amount": min_raise['value'], 
                        "position": min_raise['position'], 
                        "reasoning": "Hand in BB 3-bet range, raising"}
        
        # Check if hand is in call range
        if self.is_in_range(hero_cards, self.bb_call_range)[0]:
            if actions['CALL']['available']:
                return {"action": "CALL", "amount": None, 
                        "position": actions['CALL']['position'],
                        "reasoning": "Hand in BB call range, calling"}
        
        # Default to fold if not in any range
        if actions['FOLD']['available']:
            return {"action": "FOLD", "amount": None, 
                    "position": actions['FOLD']['position'],
                    "reasoning": "Hand not in BB defense range, folding"}
        
        # Fallback to check if somehow we can't fold
        if actions['CHECK']['available']:
            return {"action": "CHECK", "amount": None, 
                    "position": actions['CHECK']['position'],
                    "reasoning": "Defaulting to check"}
                    
        return {"action": "WAIT", "amount": None, "reasoning": "No valid action available"}
    
    def _handle_sb_vs_3bet(self, table_state: Dict) -> Dict:
        """Handle SB defense against BB 3-bet."""
        hero_cards = table_state['hero_cards']
        actions = table_state['available_actions']
        
        # Check if hand is in 4-bet range
        in_4bet_range, freq = self.is_in_range(hero_cards, self.sb_4bet_range)
        if in_4bet_range and random.random() < freq:
            # If we can raise (4-bet), do so
            if actions['R']:
                raise_options = actions['R']
                # Choose the minimum raise option
                min_raise = min(raise_options, key=lambda x: x['value'])
                return {"action": "RAISE", "amount": min_raise['value'], 
                        "position": min_raise['position'], 
                        "reasoning": "Hand in 4-bet range, raising"}
        
        # Check if hand is in call vs 3-bet range
        if self.is_in_range(hero_cards, self.sb_call_vs_3bet_range)[0]:
            if actions['CALL']['available']:
                return {"action": "CALL", "amount": None, 
                        "position": actions['CALL']['position'],
                        "reasoning": "Hand in call vs 3-bet range, calling"}
        
        # Default to fold if not in any range
        if actions['FOLD']['available']:
            return {"action": "FOLD", "amount": None, 
                    "position": actions['FOLD']['position'],
                    "reasoning": "Hand not in 3-bet defense range, folding"}
                    
        return {"action": "WAIT", "amount": None, "reasoning": "No valid action available"}