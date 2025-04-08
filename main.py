import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import cv2
import time
from src.detector.template_matcher import TemplateMatcher
from src.detector.table_detector import PokerTableDetector
from src.utils.device_connector import DeviceConnector
from src.utils.bot_controller import BotController
from src.engine.preflop_strategy import PreFlopStrategy
from src.models.hand_history import HandHistory
from src.engine.post_flop_engine import PostFlopEngine
from src.engine.claude_post_flop_engine import ClaudePostFlopEngine
from dotenv import load_dotenv
load_dotenv()  # Load environment variables for OpenAI API key

class PokerDetectorApp:
    def __init__(self):
        self.device = DeviceConnector.connect_device()
        self.template_matcher = TemplateMatcher('card_templates')
        self.table_detector = PokerTableDetector(self.template_matcher)
        self.bot_controller = BotController()
        self.preflop_strategy = PreFlopStrategy()
        
        # Choose which engine to use based on environment variable
        ai_provider = os.environ.get("AI_PROVIDER", "openai").lower()
        if ai_provider == "claude":
            print("Using Claude API for post-flop decision making")
            self.post_flop_engine = ClaudePostFlopEngine()
        else:
            print("Using OpenAI API for post-flop decision making")
            self.post_flop_engine = PostFlopEngine()

        self.current_hand = None
        self.hand_id_counter = 0
        self.last_action_taken = None

    def capture_screen(self) -> np.ndarray:
        screenshot_data = self.device.screencap()
        nparr = np.frombuffer(screenshot_data, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def print_available_actions(self, actions):
        print("\nAvailable Actions:")
        if actions['FOLD']:
            print("- FOLD")
        if actions['CALL']:
            print("- CALL")
        if actions['CHECK']:
            print("- CHECK")
        if actions['R']:
            print(f"- RAISE options: {actions['R']}")
        if actions['B']:
            print(f"- BET options: {actions['B']}")

    def click_check_button(self, current_state):
        # Now, as an example, if you want to auto-click 'CHECK'
        check_info = current_state['available_actions']['CHECK']
        if check_info['available'] and check_info['position'] is not None:
            x, y = check_info['position']
            print(f"Automatically tapping CHECK at ({x},{y})")
            self.device.shell(f"input tap {x} {y}")

            time.sleep(2)  # Wait for a second before the next action

    def check_and_click_next_hand(self) -> bool:
        """
        Check for the 'Next Hand' button and click it if detected.
        
        Returns:
            bool: True if button was found and clicked, False otherwise
        """
        screen = self.capture_screen()
        is_detected, position = self.template_matcher.detect_next_hand_button(screen)
        
        if is_detected:
            x, y = position
            print(f"Next Hand button detected at ({x}, {y}). Clicking...")
            self.device.shell(f"input tap {x} {y}")
            time.sleep(1)  # Give time for the action to take effect
            self.current_hand = None  # Reset hand history HERE instead of in run method
            self.last_action_taken = None  # Clear last action as well
            return True
        
        return False

    def start_new_hand(self, hero_cards):
        """Start tracking a new hand"""
        self.hand_id_counter += 1
        self.current_hand = HandHistory(
            hand_id=self.hand_id_counter,
            hero_cards=hero_cards
        )
        self.last_action_taken = None
        print(f"\nStarted new hand #{self.hand_id_counter}")
        
    def is_new_hand(self, current_state, previous_state):
        """Check if this is a new hand by comparing hero cards"""
        if not previous_state:
            return True
            
        # New hand if hero cards changed
        current_hero_cards = {f"{c.rank}{c.suit}" for c in current_state['hero_cards']}
        previous_hero_cards = {f"{c.rank}{c.suit}" for c in previous_state['hero_cards']}
        
        is_new = current_hero_cards != previous_hero_cards
        
        # If it's a new hand, ensure hand history is reset
        if is_new:
            print("New hand detected - cards have changed")
            self.current_hand = None  # Extra safety to clear previous hand history
            
        return is_new

    def update_hand_history(self, current_state, previous_state):
        """Update hand history with new state and actions"""
        # Identify the pre-flop scenario if we're in pre-flop or just entering post-flop

        """
        if (self.current_hand.preflop_scenario == "unknown" and 
            (current_state['street'] == "Preflop" or 
            (previous_state and previous_state['street'] == "Preflop" and current_state['street'] == "Flop"))):
            # Use the existing determine_situation method to identify scenario
            preflop_scenario = self.preflop_strategy.determine_situation(current_state)
            self.current_hand.set_preflop_scenario(preflop_scenario)
            print(f"Identified preflop scenario: {preflop_scenario}")
        """


        # Update pot type information if available and not already set
        if (self.current_hand.preflop_pot_type == "unknown" and 
            current_state.get('preflop_pot_type') and 
            current_state['preflop_pot_type'] != "unknown"):
            
            pot_type = current_state['preflop_pot_type']
            description = current_state.get('pot_type_description', '')
            
            self.current_hand.set_preflop_pot_type(pot_type, description)
            print(f"Detected pot type: {pot_type} - {description}")
        
        # If we took an action since the last state update, record it with the correct street
        if self.last_action_taken and self.last_action_taken['action'] != "WAIT":
            action_street = self.last_action_taken.get('street')
            
            # Only process actions for post-flop streets (or remove this condition to include preflop)
            if action_street != "Preflop":  # You can remove this line if you want to record preflop actions too
                self.current_hand.add_action(
                    player="hero",
                    action_type=self.last_action_taken["action"],
                    amount=self.last_action_taken.get("amount"),
                    street=action_street,  # Use the stored street
                    reasoning=self.last_action_taken.get("reasoning")
                )
            self.last_action_taken = None
            
        # Check for villain action by comparing bets (only for post-flop)
        if previous_state and previous_state['street'] != "Preflop":
            current_villain_bet = current_state['bets']['villain']
            previous_villain_bet = previous_state['bets']['villain']
            
            # If villain bet has changed, record the action
            if current_villain_bet != previous_villain_bet:
                if current_villain_bet > previous_villain_bet:
                    action_type = "RAISE" if previous_villain_bet > 0 else "BET"
                    self.current_hand.add_action(
                        player="villain",
                        action_type=action_type,
                        amount=current_villain_bet,
                        street=current_state['street'] 
                    )
        
        # After recording actions, update community cards and current street
        self.current_hand.update_community_cards(current_state['community_cards'])

    def take_action(self, current_state):
        """Take an action based on the current state and street."""
        # If it's preflop, use preflop strategy
        if current_state['street'] == "Preflop":
            action_info = self.preflop_strategy.get_action(current_state)
        else:
            # For post-flop, use the ChatGPT engine
            if self.current_hand is None:
                # Fallback if somehow we don't have hand history
                self.start_new_hand(current_state['hero_cards'])
                self.update_hand_history(current_state, None)
            
            action_info = self.post_flop_engine.get_decision(current_state, self.current_hand)
        
        action = action_info['action']
        position = action_info.get('position')
        
        if action == "WAIT":
            print("Not our turn, waiting...")
            return action_info
            
        print(f"Taking action: {action}")
        if action_info.get('amount'):
            print(f"Amount: {action_info['amount']}")
        print(f"Reasoning: {action_info['reasoning']}")
        
        if position is not None:
            x, y = position
            print(f"Tapping at ({x},{y})")
            self.device.shell(f"input tap {x} {y}")
            time.sleep(3)  # Wait for animation or next state
            
        # Store the action and the current street for hand history tracking
        action_info['street'] = current_state['street']
        self.last_action_taken = action_info
        return action_info

    def run(self):
        previous_state = None
        
        print("Bot started. Press Ctrl+C to stop.") 
        
        while self.bot_controller.should_continue():
            try:
                # First check if the next hand button is visible
                if self.check_and_click_next_hand():
                    print("Moving to next hand...")
                    time.sleep(3)  # Give extra time for next hand to load
                    self.current_hand = None  # Reset hand history
                    continue  # Skip to next iteration

                screen = self.capture_screen()
                is_hero_turn = self.table_detector.detect_hero_turn(screen)
                
                if is_hero_turn:
                    current_state = self.table_detector.detect_table_state(screen)
                    
                    # Check if this is a new hand
                    if self.is_new_hand(current_state, previous_state):
                        self.start_new_hand(current_state['hero_cards'])
                    
                    if self._has_state_changed(previous_state, current_state):
                        # Update hand history based on changes
                        if self.current_hand:
                            self.update_hand_history(current_state, previous_state)
                        
                        print("\n=== Table State ===")
                        print(f"Street: {current_state['street']}")
                        print("Hero cards:", [f"{c.rank}{c.suit}" for c in current_state['hero_cards']])
                        print("Community cards:", [f"{c.rank}{c.suit}" for c in current_state['community_cards']])
                        print(f"Hero stack: ${current_state['stacks']['hero']:.2f}")
                        print(f"Villain stack: ${current_state['stacks']['villain']:.2f}")
                        print(f"Hero bet: ${current_state['bets']['hero']:.2f}")
                        print(f"Villain bet: ${current_state['bets']['villain']:.2f}")
                        print(f"Pot size: ${current_state['pot_size']:.2f}")
                        print(f"Positions: {current_state['positions']}")
                        print(f"preflop_pot_type: {current_state['preflop_pot_type']}")
                        
                        # Print hand history
                        if self.current_hand:
                            print("\n=== Hand History ===")
                            print(self.current_hand.format_history())
                            
                        print("================")
                        
                        # Print available actions
                        print("\nAvailable Actions with Button Locations:")
                        for action, data in current_state['available_actions'].items():
                            if action in ['FOLD', 'CALL', 'CHECK']:
                                if data.get('available'):
                                    print(f"{action}: {data}")
                            else:  # For 'R' and 'B'
                                if data:  # List not empty
                                    print(f"{action}: {data}")

                        # Take action
                        self.take_action(current_state)
                        
                        previous_state = current_state
                
                time.sleep(1)
                
            except Exception as e:
                print(f"Error occurred: {e}")
                import traceback
                traceback.print_exc()
                break
        
        self.cleanup()

    def _has_state_changed(self, previous_state, current_state):
        if previous_state is None:
            return True
            
        # Compare relevant state components
        return (
            previous_state['hero_cards'] != current_state['hero_cards'] or
            previous_state['community_cards'] != current_state['community_cards'] or
            previous_state['bets'] != current_state['bets'] or
            previous_state['pot_size'] != current_state['pot_size'] or
            previous_state['street'] != current_state['street'] or
            previous_state['available_actions'] != current_state['available_actions'] or
            previous_state['positions'] != current_state['positions']
        )
    
    def cleanup(self):
        self.bot_controller.cleanup()
        cv2.destroyAllWindows()

def main():
    app = PokerDetectorApp()

    try:
        app.run()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    finally:
        app.cleanup()

if __name__ == "__main__":
    main()