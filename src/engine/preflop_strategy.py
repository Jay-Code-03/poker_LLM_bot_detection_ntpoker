# src/engine/preflop_strategy.py
from typing import Dict, Tuple, List, Optional
import random
from src.models.card import Card

class PreFlopStrategy:
    def __init__(self):
        # Initialize with the SB open raise range
        self.sb_open_range = self._parse_range("AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AK,AQ,AJ,AT,A9,A8,A7,A6,A5,A4,A3,A2,KQ,KJ,KT,K9,K8,K7,K6,K5,K4,K3,K2,QJ,QT,Q9,Q8,Q7,Q6,Q5,Q4,Q3,Q2s,Q2o:0.5,JT,J9,J8,J7,J6,J5,J4s,J3s,J2s,T9,T8,T7,T6,T5,T4s,T3s,T2s,98,97,96,95,94s,93s,92s,87,86,85,84s,83s,82s,76,75,74s,73s,72s,65,64s,63s,62s,54s,53s,52s,43s,42s,32s")
        
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
            
    def is_in_range(self, cards: List[Card]) -> Tuple[bool, float]:
        """Check if a hand is in the range and return its frequency."""
        hand = self._normalize_hand(cards)
        
        # Handle special case for pairs
        if len(hand) >= 2 and hand[0] == hand[1]:
            hand = hand[:2]
            
        # First try exact match
        if hand in self.sb_open_range:
            return True, self.sb_open_range[hand]
            
        # If not found, try without the 'o' suffix for offsuit hands
        if hand.endswith('o') and hand[:-1] in self.sb_open_range:
            return True, self.sb_open_range[hand[:-1]]
            
        return False, 0.0
        
    def should_play(self, cards: List[Card]) -> bool:
        """Determine if a hand should be played based on the range and frequencies."""
        in_range, freq = self.is_in_range(cards)
        
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
        
        # Check if hero is SB and villain hasn't acted
        if positions.get('SB') == 'hero' and table_state['bets']['villain'] == 1:
            return "sb_open"
            
        return "unknown"

    def get_action(self, table_state: Dict) -> Dict:
        """Determine the action to take based on the current state."""
        hero_cards = table_state['hero_cards']
        
        # If not our turn, do nothing
        if not table_state['is_hero_turn']:
            return {"action": "WAIT", "amount": None, "reasoning": "Not our turn"}
            
        # Determine the situation
        situation = self.determine_situation(table_state)
        
        if situation != "sb_open":
            return {"action": "FOLD", "amount": None, 
                    "reasoning": f"Only handling SB open for now, situation: {situation}"}
            
        # Check if our hand is in the range
        if self.should_play(hero_cards):
            return self._choose_action_in_range(table_state)
        else:
            return self._choose_action_not_in_range(table_state)
        
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