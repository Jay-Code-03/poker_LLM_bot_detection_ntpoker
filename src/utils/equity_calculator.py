# src/utils/equity_calculator.py
import eval7
import os
import random
from typing import List, Dict, Optional, Tuple
from src.models.card import Card as PokerCard

class EquityCalculator:
    def __init__(self, ranges_dir="ranges"):
        """Initialize the equity calculator with preflop ranges"""
        self.ranges_dir = ranges_dir
        print(f"Initializing EquityCalculator with ranges directory: {ranges_dir}")
        
        # Check if ranges directory exists
        if not os.path.exists(ranges_dir):
            print(f"WARNING: Ranges directory {ranges_dir} does not exist")
        
        self.raw_ranges = self._load_all_raw_ranges()
        
    def _load_all_raw_ranges(self) -> Dict[str, Dict[str, float]]:
        """Load all preflop ranges from files as dictionaries with weights"""
        range_files = {
            "sb_open": "sb_open.txt",
            "bb_call": "bb_call.txt",
            "bb_3bet": "bb_3bet.txt",
            "sb_call_vs_3bet": "sb_call_vs_3bet.txt",
            "sb_4bet": "sb_4bet.txt",
            "bb_call_vs_4bet": "bb_call_vs_4bet.txt",
            "bb_5bet": "bb_5bet.txt", 
            "sb_call_vs_5bet": "sb_call_vs_5bet.txt"
        }
        
        raw_ranges = {}
        for name, filename in range_files.items():
            filepath = os.path.join(self.ranges_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    range_str = f.read().strip()
                # Parse into dictionary with weights
                raw_ranges[name] = self._parse_range_weights(range_str)
                print(f"Successfully loaded range '{name}' with {len(raw_ranges[name])} hands")
            except Exception as e:
                print(f"Error loading range '{name}' from {filepath}: {e}")
                # Create empty range as fallback
                raw_ranges[name] = {"AA": 1.0, "KK": 1.0, "QQ": 1.0, "AKs": 1.0}
                print(f"Using fallback range for '{name}'")
                
        return raw_ranges
    
    def _parse_range_weights(self, range_str: str) -> Dict[str, float]:
        """
        Parse range string into dictionary with weights
        
        Example:
        "AA,KK,QQ:0.75,JJ:0.5" -> {"AA": 1.0, "KK": 1.0, "QQ": 0.75, "JJ": 0.5}
        """
        result = {}
        parts = range_str.split(',')
        
        for part in parts:
            if ':' in part:
                hand, weight = part.split(':')
                result[hand] = float(weight)
            else:
                result[part] = 1.0
                
        return result
    
    def _create_weighted_range(self, range_dict: Dict[str, float]) -> eval7.HandRange:
        """
        Create an eval7.HandRange by randomly selecting hands based on their weights
        
        For each hand in the range dictionary:
        - Generate random number between 0-1
        - If random number < weight, include the hand in the range
        - Otherwise, exclude it
        """
        selected_hands = []
        
        for hand, weight in range_dict.items():
            # Generate a random number and compare to weight
            if random.random() < weight:
                selected_hands.append(hand)
        
        # If no hands were selected (unlikely but possible), add a default hand
        if not selected_hands:
            selected_hands = ["AA", "KK", "QQ"]
            
        # Create range string and convert to eval7.HandRange
        range_str = ",".join(selected_hands)
        try:
            return eval7.HandRange(range_str)
        except Exception as e:
            print(f"Error creating HandRange from string '{range_str}': {e}")
            # Fallback to a minimal range
            return eval7.HandRange("AA")
    
    def convert_card(self, card: PokerCard) -> Optional[eval7.Card]:
        """
        Convert app's Card object to eval7.Card
        
        Args:
            card: Card object with rank and suit attributes
        """
        # Map our suit format to eval7's
        suit_map = {
            'h': 'h', 'H': 'h',
            'd': 'd', 'D': 'd',
            's': 's', 'S': 's',
            'c': 'c', 'C': 'c'
        }
        
        # Handle ranks correctly
        rank_map = {
            't': 'T', 'T': 'T',
            'j': 'J', 'J': 'J',
            'q': 'Q', 'Q': 'Q',
            'k': 'K', 'K': 'K',
            'a': 'A', 'A': 'A'
        }
        
        # Get formatted rank and suit
        rank = rank_map.get(card.rank, card.rank.upper())
        suit = suit_map.get(card.suit, card.suit.lower())
        
        # Double-check valid ranks and suits
        valid_ranks = set(['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A'])
        valid_suits = set(['h', 'd', 's', 'c'])
        
        if rank not in valid_ranks:
            print(f"ERROR: Invalid rank '{rank}' from '{card.rank}'")
            return None
            
        if suit not in valid_suits:
            print(f"ERROR: Invalid suit '{suit}' from '{card.suit}'")
            return None
        
        # Create the card
        try:
            return eval7.Card(f"{rank}{suit}")
        except Exception as e:
            print(f"Error creating eval7.Card('{rank}{suit}'): {e}")
            return None
    
    def _determine_range_key(self, pot_type: str, hero_position: str) -> str:
        """
        Determine which range to use based on pot type and positions
        
        Args:
            pot_type: e.g., "2_bet_pot", "3_bet_pot", "4_bet_pot"
            hero_position: "SB" or "BB"
        """
        # Villain position is opposite of hero
        villain_position = "BB" if hero_position == "SB" else "SB"
        
        # Match pot type to the appropriate range
        if pot_type == "2_bet_pot":  # SB open, BB call
            if villain_position == "BB":
                return "bb_call"
            else:
                return "sb_open"
                
        elif pot_type == "3_bet_pot":  # SB open, BB 3-bet, SB call
            if villain_position == "BB":
                return "bb_3bet"
            else:
                return "sb_call_vs_3bet"
                
        elif pot_type == "4_bet_pot":  # SB open, BB 3-bet, SB 4-bet, BB call
            if villain_position == "BB":
                return "bb_call_vs_4bet"
            else:
                return "sb_4bet"
                
        # Default to a wide range if we can't determine
        return "sb_open" if villain_position == "SB" else "bb_call"
    
    def estimate_villain_range(self, preflop_pot_type: str, 
                               hero_position: str,
                               board_cards: List[PokerCard]) -> Tuple[eval7.HandRange, str]:
        """
        Estimate villain's range based on preflop pot type, positions, and actions
        
        Returns:
            Tuple of (HandRange object, description string)
        """
        # Convert board cards to eval7 format
        board = [self.convert_card(card) for card in board_cards]
        board = [card for card in board if card is not None]
        
        # Get the appropriate range key
        range_key = self._determine_range_key(preflop_pot_type, hero_position)
        
        # Try creating a very simple range first as a test
        try:
            test_range = eval7.HandRange("AA,KK")
        except Exception as e:
            print(f"ERROR creating test range: {e}")
            # If basic range creation fails, use simplest possible range
            return eval7.HandRange("AA"), "Default range (test failed)"
        
        # Get the base range dictionary with weights
        if range_key in self.raw_ranges:
            base_range_dict = self.raw_ranges[range_key]
            description = f"Based on preflop action ({range_key.replace('_', ' ')})"
        else:
            # Fallback to a reasonable default range
            base_range_dict = {"AA": 1.0, "KK": 1.0, "QQ": 1.0, "JJ": 1.0, "TT": 1.0, 
                              "AK": 1.0, "AQ": 1.0, "AJ": 1.0, "KQ": 1.0}
            description = "Default range (preflop pattern not recognized)"
        
        # Create a weighted range using our RNG method
        weighted_range = self._create_weighted_range(base_range_dict)
        
        return weighted_range, description
    
    def calculate_equity(self, 
                          hero_cards: List[PokerCard], 
                          board_cards: List[PokerCard],
                          preflop_pot_type: str,
                          hand_history=None,
                          iterations: int = 1000) -> Dict:
        """
        Calculate equity of hero's hand versus villain's estimated range
        
        Args:
            hero_cards: List of Card objects (each with rank and suit attributes)
            board_cards: List of Card objects
            preflop_pot_type: String like "2_bet_pot", "3_bet_pot", "4_bet_pot"
            hand_history: Optional hand history object
            iterations: Number of Monte Carlo simulations to run
            
        Returns:
            Dictionary with equity calculation results
        """
        print(f"\n=== CALCULATING EQUITY ===")
        print(f"Hero cards: {[f'{c.rank}{c.suit}' for c in hero_cards]}")
        print(f"Board cards: {[f'{c.rank}{c.suit}' for c in board_cards]}")
        print(f"Preflop pot type: {preflop_pot_type}")
        
        # Determine hero position
        hero_position = "BB"  # Default
        if hand_history and hasattr(hand_history, 'positions'):
            positions = hand_history.positions
            hero_position = "SB" if positions.get('SB') == 'hero' else "BB"
        
        print(f"Hero position: {hero_position}")
        
        # Convert card objects to eval7 cards
        hero_hand = [self.convert_card(card) for card in hero_cards]
        hero_hand = [card for card in hero_hand if card is not None]
        
        board = [self.convert_card(card) for card in board_cards]
        board = [card for card in board if card is not None]
        
        print(f"Converted hero hand: {[str(card) for card in hero_hand]}")
        print(f"Converted board: {[str(card) for card in board]}")
        
        # Check if we have valid cards
        if len(hero_hand) != 2:
            print(f"ERROR: Invalid hero hand - need exactly 2 cards, got {len(hero_hand)}")
            return {"error": "Invalid hero hand"}
            
        try:
            # Estimate villain's range
            villain_range, range_description = self.estimate_villain_range(
                preflop_pot_type, 
                hero_position, 
                board_cards
            )
            
            print(f"Villain range description: {range_description}")
            print(f"Calculating equity with {iterations} iterations...")
            
            # Calculate equity
            equity = eval7.py_hand_vs_range_monte_carlo(
                hero_hand,
                villain_range,
                board,
                iterations
            )
            
            print(f"Equity result: {equity * 100:.2f}%")
            
            # Format equity info for display
            equity_info = f"\n=== EQUITY CALCULATION RESULT ===\n"
            equity_info += f"Hero hand: {[str(card) for card in hero_hand]}\n"
            equity_info += f"Board: {[str(card) for card in board]}\n"
            equity_info += f"Equity vs. range: {equity * 100:.2f}%\n"
            equity_info += f"Villain range: {range_description}\n"
            equity_info += f"Based on {iterations} Monte Carlo simulations\n"
            
            print(equity_info)
            
            return {
                "equity": equity,
                "villain_range": str(villain_range),
                "range_description": range_description,
                "iterations": iterations
            }
            
        except Exception as e:
            import traceback
            print(f"Error calculating equity: {e}")
            print(traceback.format_exc())
            return {"error": str(e)}