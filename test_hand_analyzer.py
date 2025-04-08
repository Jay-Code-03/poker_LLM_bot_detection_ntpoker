from dataclasses import dataclass
from treys import Card as TreysCard
from treys import Evaluator

@dataclass
class Card:
    rank: str
    suit: str
    confidence: float = 1.0
    
    def __repr__(self):
        return f"{self.rank}{self.suit}"

class HandAnalyzer:
    def __init__(self):
        self.evaluator = Evaluator()
        self.rank_values = {
            '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 
            'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
        }
    
    def convert_card(self, card):
        """Convert your Card object to Treys format"""
        return TreysCard.new(f"{card.rank}{card.suit.lower()}")
    
    def analyze_hand(self, hero_cards, board_cards):
        """Comprehensive poker hand analysis"""
        # If no board cards, return minimal analysis
        if not board_cards:
            return {"hand_type": "No community cards", "draws": {}}
        
        # Convert cards to Treys format
        treys_hero = [self.convert_card(card) for card in hero_cards]
        treys_board = [self.convert_card(card) for card in board_cards]
        
        result = {}
        
        # Basic hand evaluation
        if board_cards:
            score = self.evaluator.evaluate(treys_board, treys_hero)
            class_index = self.evaluator.get_rank_class(score)
            result["hand_type"] = self.evaluator.class_to_string(class_index)
        
        # Detailed pair analysis for pair hands
        hand_type_lower = result.get("hand_type", "").lower()
        if "pair" in hand_type_lower:
            pair_description = self._analyze_pair_strength(hero_cards, board_cards)
            result["pair_description"] = pair_description
        
        # Skip draw analysis for already completed strong hands
        completed_hands = ["straight", "flush", "full house", "four of a kind", "straight flush", "royal flush"]
        if any(hand_type in hand_type_lower for hand_type in completed_hands):
            result["draws"] = {
                "flush_draw": False,
                "backdoor_flush_draw": False,
                "straight_draw": False,
                "backdoor_straight_draw": False,
                "flush_draw_info": "N/A - Already have completed hand",
                "straight_draw_info": "N/A - Already have completed hand"
            }
            return result
        
        # Draw analysis (requires at least 3 board cards)
        result["draws"] = {}
        if len(board_cards) >= 3:
            # Analyze flush draws
            result["draws"].update(self._analyze_flush_draws(hero_cards, board_cards))
            # Analyze straight draws
            result["draws"].update(self._analyze_straight_draws(hero_cards, board_cards))
        
        return result
    
    # All other methods remain the same
    def _analyze_pair_strength(self, hero_cards, board_cards):
        """Determine if we have top pair, second pair, etc."""
        # Get ranks as integers
        hero_ranks = [self.rank_values[card.rank] for card in hero_cards]
        board_ranks = [self.rank_values[card.rank] for card in board_cards]
        
        # Sort board ranks from highest to lowest
        board_ranks_sorted = sorted(board_ranks, reverse=True)
        
        # Check for pocket pair
        if hero_ranks[0] == hero_ranks[1]:
            pair_rank = hero_ranks[0]
            if pair_rank > max(board_ranks):
                return "Overpair"
            elif pair_rank < max(board_ranks):
                return "Underpair"
            else:
                return "Pocket pair with top card"
        
        # Check for pair with board
        for hero_rank in hero_ranks:
            if hero_rank in board_ranks:
                if hero_rank == board_ranks_sorted[0]:
                    return "Top pair"
                elif len(board_ranks) > 1 and hero_rank == board_ranks_sorted[1]:
                    return "Second pair"
                elif len(board_ranks) > 2 and hero_rank == board_ranks_sorted[2]:
                    return "Third pair"
                else:
                    return "Bottom pair"
        
        return "No pair detected"
    
    def _analyze_flush_draws(self, hero_cards, board_cards):
        """Detect flush draws and backdoor flush draws"""
        all_cards = hero_cards + board_cards
        
        # Count suits
        suits = {}
        for card in all_cards:
            suits[card.suit] = suits.get(card.suit, 0) + 1
        
        # Check which suits hero has
        hero_suits = {card.suit for card in hero_cards}
        
        result = {
            "flush_draw": False,
            "backdoor_flush_draw": False,
            "flush_draw_info": ""
        }
        
        # Regular flush draw (4 cards to a flush)
        for suit, count in suits.items():
            if count >= 4 and suit in hero_suits:
                result["flush_draw"] = True
                result["flush_draw_info"] = f"{suit} flush draw"
                break
        
        # Backdoor flush draw (3 cards to a flush on flop)
        if not result["flush_draw"] and len(board_cards) == 3:
            for suit, count in suits.items():
                if count == 3 and suit in hero_suits:
                    result["backdoor_flush_draw"] = True
                    result["flush_draw_info"] = f"Backdoor {suit} flush draw"
                    break
        
        return result
    
    def _analyze_straight_draws(self, hero_cards, board_cards):
        """Detect straight draws and backdoor straight draws"""
        # Get all ranks as values
        all_ranks = []
        for card in hero_cards + board_cards:
            all_ranks.append(self.rank_values[card.rank])
        
        # Add low ace for A-5 straights
        if 14 in all_ranks:
            all_ranks.append(1)
        
        # Sort and remove duplicates
        unique_ranks = sorted(set(all_ranks))
        
        result = {
            "straight_draw": False,
            "backdoor_straight_draw": False,
            "straight_draw_info": ""
        }
        
        # Special handling for A-2-3-4 (needs 5) gutshot
        if set([1, 2, 3, 4]).issubset(set(unique_ranks)):
            result["straight_draw"] = True
            result["straight_draw_info"] = "Gutshot straight draw (needs: 5)"
            return result
        
        # Fixed straight draw detection
        if len(unique_ranks) >= 4:  # Need at least 4 ranks to have a straight draw
            # Look for sequences and potential draws
            for i in range(len(unique_ranks) - 3):
                window = unique_ranks[i:i+4]
                span = window[-1] - window[0]
                
                # Check if we have 4 consecutive ranks (open-ended)
                if span == 3:  # 4 consecutive cards like 5-6-7-8
                    # Can complete with card below or above
                    lower_out = window[0] - 1
                    upper_out = window[-1] + 1
                    
                    # Convert numerical ranks back for display
                    rank_map = {1: 'A', 14: 'A', 13: 'K', 12: 'Q', 11: 'J', 10: 'T'}
                    lower_out_str = rank_map.get(lower_out, str(lower_out))
                    upper_out_str = rank_map.get(upper_out, str(upper_out))
                    
                    # Skip if out cards are out of range
                    outs = []
                    if lower_out >= 2:  # 2 is lowest card
                        outs.append(lower_out_str)
                    if upper_out <= 14:  # A is highest card
                        outs.append(upper_out_str)
                    
                    result["straight_draw"] = True
                    result["straight_draw_info"] = f"Open-ended straight draw (needs: {', '.join(outs)})"
                    break
                
                # Gutshot check - exactly one gap in a 5-card sequence
                elif span == 4:  # 4 cards with a gap like 5-6-8-9
                    # Find the missing rank
                    missing = None
                    for j in range(window[0], window[-1]):
                        if j not in window:
                            # Convert to letter rank if needed
                            rank_map = {1: 'A', 14: 'A', 13: 'K', 12: 'Q', 11: 'J', 10: 'T'}
                            missing = rank_map.get(j, str(j))
                            break
                    
                    result["straight_draw"] = True
                    result["straight_draw_info"] = f"Gutshot straight draw (needs: {missing})"
                    break
        
        # Only check for backdoor draws if no regular draws found and we're on the flop
        if not result["straight_draw"] and len(board_cards) == 3:
            # Check for 3 consecutive ranks (potential backdoor straight)
            for i in range(len(unique_ranks) - 2):
                if unique_ranks[i+2] - unique_ranks[i] == 2:  # Exactly 3 consecutive cards
                    result["backdoor_straight_draw"] = True
                    result["straight_draw_info"] = "Backdoor straight draw"
                    break
                # 3 cards spanning 4 ranks - needs two specific cards
                elif unique_ranks[i+2] - unique_ranks[i] <= 4:  # 3 cards within 5-card span
                    result["backdoor_straight_draw"] = True
                    result["straight_draw_info"] = "Backdoor straight draw"
                    break
        
        return result


def create_cards(card_strings):
    """Helper function to create cards from strings"""
    cards = []
    for card_str in card_strings:
        rank = card_str[0]
        suit = card_str[1]
        cards.append(Card(rank, suit))
    return cards

def print_analysis(hero_cards, board_cards, analysis):
    """Display analysis in a readable format"""
    print(f"Hero: {', '.join(str(card) for card in hero_cards)}")
    print(f"Board: {', '.join(str(card) for card in board_cards)}")
    print(f"Hand type: {analysis.get('hand_type', 'N/A')}")
    
    # This is the important fix - display pair description when available
    if 'pair_description' in analysis:
        print(f"Pair description: {analysis['pair_description']}")
    
    draws = analysis.get('draws', {})
    if draws:
        if draws.get('flush_draw', False):
            print(f"Flush draw: Yes - {draws.get('flush_draw_info', '')}")
        elif draws.get('backdoor_flush_draw', False):
            print(f"Backdoor flush draw: Yes - {draws.get('flush_draw_info', '')}")
        else:
            print("Flush draw: No")
        
        if draws.get('straight_draw', False):
            print(f"Straight draw: Yes - {draws.get('straight_draw_info', '')}")
        elif draws.get('backdoor_straight_draw', False):
            print(f"Backdoor straight draw: Yes - {draws.get('straight_draw_info', '')}")
        else:
            print("Straight draw: No")
    
    print("\n" + "-"*50 + "\n")

def run_tests():
    """Run various test cases"""
    analyzer = HandAnalyzer()
    
    # Test 1: Original example (Ad9s on Jh6c5s)
    test_case("Ad 9s", "Jh 6c 5s", analyzer, "High card with backdoor straight draw")
    
    # Test 2: Top pair
    test_case("Ah Tc", "Ad Ks 2h", analyzer, "Top pair")
    
    # Test 3: Second pair
    test_case("Kh 8c", "As Kd 4c", analyzer, "Second pair")
    
    # Test 4: Overpair
    test_case("Qh Qc", "Js 9d 2h", analyzer, "Overpair")
    
    # Test 5: Flush draw
    test_case("Ah 9h", "Kh 2h 5s", analyzer, "Flush draw")
    
    # Test 6: Backdoor flush draw
    test_case("As 3s", "Ks 7d 9c", analyzer, "Backdoor flush draw")
    
    # Test 7: Open-ended straight draw
    test_case("8h 9c", "7s Td 2h", analyzer, "Open-ended straight draw")
    
    # Test 8: Gutshot straight draw
    test_case("8h Tc", "7s Jd 2h", analyzer, "Gutshot straight draw")
    
    # Test 9: Two pair
    test_case("Ah 9c", "Ad 9d 2h", analyzer, "Two pair")
    
    # Test 10: Set
    test_case("9h 9c", "9d Kd 2h", analyzer, "Set (three of a kind)")
    
    # Test 11: Full house
    test_case("9h 9c", "9d Kd Kh", analyzer, "Full house")
    
    # Test 12: Ace-high flush draw
    test_case("Ah Jh", "2h 5h 9c", analyzer, "Flush draw with Ace high")
    
    # Test 13: Ace-to-five straight draw
    test_case("Ah 2c", "3d 4s 8c", analyzer, "Straight draw involving Ace-to-five")
    
    # Test 14: Complete flush
    test_case("Ah Jh", "2h 5h 9h", analyzer, "Completed flush")
    
    # Test 15: Complete straight
    test_case("9h Tc", "7s 8d Jh", analyzer, "Completed straight")

def test_case(hero_str, board_str, analyzer, description):
    """Run a single test case"""
    print(f"Testing: {description}")
    hero = create_cards(hero_str.split())
    board = create_cards(board_str.split())
    analysis = analyzer.analyze_hand(hero, board)
    print_analysis(hero, board, analysis)


if __name__ == "__main__":
    run_tests()