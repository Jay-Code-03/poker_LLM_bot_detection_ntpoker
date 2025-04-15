# src/utils/logger.py
import os
import json
import datetime
import time
from typing import Dict, Any

class PokerBotLogger:
    def __init__(self, log_dir="logs"):
        """Initialize the logger with appropriate directories"""
        # Create timestamp for this session
        self.session_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create log directory if it doesn't exist
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Create session directory
        self.session_dir = os.path.join(self.log_dir, f"session_{self.session_timestamp}")
        os.makedirs(self.session_dir, exist_ok=True)
        
        # Paths for different log files
        self.text_log_path = os.path.join(self.session_dir, "session.log")
        self.json_log_path = os.path.join(self.session_dir, "session.json")
        
        # Initialize the json log file with an empty list
        with open(self.json_log_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        
        # Log session start
        self.log_text(f"=== Poker Bot Session Started at {self.session_timestamp} ===")
        
    def log_text(self, message: str):
        """Log a text message to the text log file"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.text_log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
            
    def log_table_state(self, state: Dict[str, Any], hand_id: int):
        """Log the current table state"""
        # Format the state for text log
        hero_cards = [f"{c.rank}{c.suit}" for c in state['hero_cards']]
        community_cards = [f"{c.rank}{c.suit}" for c in state['community_cards']]
        
        text_state = (
            f"\n=== TABLE STATE (Hand #{hand_id}) ===\n"
            f"Street: {state['street']}\n"
            f"Hero cards: {', '.join(hero_cards)}\n"
            f"Community cards: {', '.join(community_cards)}\n"
            f"Hero stack: ${state['stacks']['hero']:.2f}\n"
            f"Villain stack: ${state['stacks']['villain']:.2f}\n"
            f"Hero bet: ${state['bets']['hero']:.2f}\n"
            f"Villain bet: ${state['bets']['villain']:.2f}\n"
            f"Pot size: ${state['pot_size']:.2f}\n"
            f"Positions: {state['positions']}\n"
            f"Pot type: {state.get('preflop_pot_type', 'unknown')}\n"
        )
        
        self.log_text(text_state)
        
        # Also log to JSON
        self._append_to_json_log({
            "type": "table_state",
            "timestamp": time.time(),
            "hand_id": hand_id,
            "data": self._prepare_state_for_json(state)
        })
        
    def log_action(self, action_info: Dict[str, Any], hand_id: int):
        """Log an action taken by the bot"""
        action = action_info["action"]
        amount = action_info.get("amount")
        reasoning = action_info.get("reasoning", "No reasoning provided")
        
        amount_str = f" ${amount:.2f}" if amount is not None else ""
        
        text_action = (
            f"\n=== ACTION TAKEN (Hand #{hand_id}) ===\n"
            f"Action: {action}{amount_str}\n"
            f"Reasoning: {reasoning}\n"
        )
        
        self.log_text(text_action)
        
        # Also log to JSON
        self._append_to_json_log({
            "type": "action",
            "timestamp": time.time(),
            "hand_id": hand_id,
            "data": {
                "action": action,
                "amount": amount,
                "reasoning": reasoning
            }
        })
        
    def log_hand_summary(self, hand_history, hand_id: int):
        """Log a summary of the completed hand"""
        # Check for duplicate hand summary in the last 5 entries
        text_summary = f"\n=== HAND SUMMARY (Hand #{hand_id}) ===\n{hand_history.format_history()}\n"
        
        # Check if this exact text is already at the end of the file
        try:
            with open(self.text_log_path, 'r', encoding='utf-8') as f:
                last_lines = f.read().strip().split("\n=== HAND SUMMARY")[-1]
            
            # If this exact summary was just logged, skip
            if text_summary.strip() in last_lines:
                return
        except:
            pass  # If we can't read the file, just proceed with logging
        
        # Proceed with normal logging
        text_summary += "=" * 40 + "\n"
        self.log_text(text_summary)
        
        # Also log to JSON
        self._append_to_json_log({
            "type": "hand_summary",
            "timestamp": time.time(),
            "hand_id": hand_id,
            "data": {
                "preflop_pot_type": hand_history.preflop_pot_type,
                "pot_type_description": hand_history.pot_type_description,
                "hero_cards": [f"{c.rank}{c.suit}" for c in hand_history.hero_cards],
                "community_cards": [f"{c.rank}{c.suit}" for c in hand_history.community_cards],
                "actions": [
                    {
                        "street": action.street,
                        "player": action.player,
                        "action_type": action.action_type,
                        "amount": action.amount,
                        "reasoning": action.reasoning
                    }
                    for action in hand_history.actions
                ]
            }
        })
    
    def _prepare_state_for_json(self, state: Dict) -> Dict:
        """Convert state objects to serializable format for JSON"""
        # Deep copy and convert non-serializable objects
        serializable = {}
        
        # Convert Card objects to strings
        serializable["hero_cards"] = [f"{c.rank}{c.suit}" for c in state['hero_cards']]
        serializable["community_cards"] = [f"{c.rank}{c.suit}" for c in state['community_cards']]
        
        # Copy other fields directly
        for key in ['stacks', 'bets', 'pot_size', 'positions', 'street', 'preflop_pot_type']:
            if key in state:
                serializable[key] = state[key]
        
        return serializable
        
    def _append_to_json_log(self, data: Dict):
        """Append a data entry to the JSON log file"""
        try:
            # Read existing data
            with open(self.json_log_path, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            
            # Append new data
            log_data.append(data)
            
            # Write back
            with open(self.json_log_path, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, indent=2)
        except Exception as e:
            # If JSON logging fails, log the error to text file
            self.log_text(f"ERROR: Failed to write to JSON log: {e}")
    
    def close(self):
        """Close the logger and finalize logs"""
        self.log_text(f"=== Poker Bot Session Ended at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")