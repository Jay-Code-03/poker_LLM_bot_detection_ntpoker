# src/engine/claude_post_flop_engine.py
from anthropic import Anthropic
from typing import Dict, List
import json
import os
from src.utils.hand_analyzer import HandAnalyzer  # Import the new HandAnalyzer

class ClaudePostFlopEngine:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = Anthropic(api_key=api_key)
        self.hand_analyzer = HandAnalyzer()  # Initialize the hand analyzer
    
    def interpret_preflop_scenario(self, scenario: str) -> str:
        """Convert preflop scenario code to a detailed explanation"""
        scenario_descriptions = {
            "sb_open": "Small blind opened with a raise. This is an open-raising situation where SB takes the initiative.",
            "bb_defense": "Small blind raised, and big blind defended (called or 3-bet). This is a situation where BB is responding to a SB open.",
            "sb_vs_3bet": "Small blind opened, big blind 3-bet, and small blind is now facing this 3-bet. The pot is already larger than normal and ranges are narrower.",
            "bb_vs_4bet": "Small blind opened, big blind 3-bet, small blind 4-bet, and big blind is now facing this 4-bet. This indicates very strong ranges on both sides.",
            "sb_vs_5bet": "This is a 5-bet pot where ranges are extremely polarized (very strong hands or bluffs). Pot is very large compared to starting stacks.",
            "unknown": "The preflop action couldn't be determined precisely. We'll need to make decisions based on the current situation.",
            "not_preflop": "N/A - already in post-flop"
        }
        return scenario_descriptions.get(scenario, f"Unknown scenario: {scenario}")
        
    def format_game_state(self, table_state: Dict, hand_history) -> str:
        """Format the table state and hand history into a clear prompt for the LLM"""
        hero_cards = table_state['hero_cards']
        hero_cards_str = [f"{c.rank}{c.suit}" for c in hero_cards]
        
        community_cards = table_state['community_cards']
        community_cards_str = [f"{c.rank}{c.suit}" for c in community_cards]
        
        positions = table_state.get('positions', {})
        hero_position = "SB" if positions.get('SB') == 'hero' else "BB"
        villain_position = "SB" if positions.get('SB') == 'villain' else "BB"
        
        pot_type_info = ""
        if hand_history.preflop_pot_type != "unknown":
            pot_type_info = f"\nCurrent pot type: {hand_history.preflop_pot_type} ({hand_history.pot_type_description})"
        
        # Get accurate hand analysis
        hand_analysis = self.hand_analyzer.analyze_hand(hero_cards, community_cards)
        
        analysis_text = "## Hand Analysis (Mathematically Verified):\n"
        
        # Add hand type information
        if community_cards:
            analysis_text += f"- Current hand: {hand_analysis.get('hand_type', 'High Card')}\n"
            if 'pair_description' in hand_analysis:
                analysis_text += f"- Pair strength: {hand_analysis['pair_description']}\n"
        
        # Add draw information
        draws = hand_analysis.get('draws', {})
        if draws:
            # Flush draw info
            if draws.get('flush_draw', False):
                analysis_text += f"- Flush draw: Yes - {draws.get('flush_draw_info', '')}\n"
            elif draws.get('backdoor_flush_draw', False):
                analysis_text += f"- Backdoor flush draw: Yes - {draws.get('flush_draw_info', '')}\n"
            else:
                analysis_text += "- Flush draw: No\n"
            
            # Straight draw info
            if draws.get('straight_draw', False):
                analysis_text += f"- Straight draw: Yes - {draws.get('straight_draw_info', '')}\n"
            elif draws.get('backdoor_straight_draw', False):
                analysis_text += f"- Backdoor straight draw: Yes - {draws.get('straight_draw_info', '')}\n"
            else:
                analysis_text += "- Straight draw: No\n"
        
        # Calculate pot odds
        if len(community_cards) >= 3 and table_state['bets']['villain'] > table_state['bets']['hero']:
            to_call = table_state['bets']['villain'] - table_state['bets']['hero']
            pot_after_call = table_state['pot_size'] + to_call
            pot_odds = to_call / pot_after_call
            analysis_text += f"- Pot odds: {pot_odds:.2f} (need {pot_odds*100:.1f}% equity to call)\n"
    
        state_prompt = f"""
# Current Poker Situation (Heads-Up No-Limit Hold'em)

## Pre-flop Context:
{pot_type_info}

## Hand Information:
- Hero position: {hero_position}
- Villain position: {villain_position}
- Street: {table_state['street']}

## Cards:
- Hero cards: {', '.join(hero_cards_str)}
- Community cards: {', '.join(community_cards_str)}

{analysis_text}

## Stack and Pot Information:
- Pot size: ${table_state['pot_size']:.2f}
- Hero stack: ${table_state['stacks']['hero']:.2f}
- Villain stack: ${table_state['stacks']['villain']:.2f}
- Hero bet: ${table_state['bets']['hero']:.2f}
- Villain bet: ${table_state['bets']['villain']:.2f}

## Current Hand Action History:
{hand_history.format_history()}

## Available Actions:"""
        
        actions = table_state['available_actions']
        if actions.get('FOLD', {}).get('available', False):
            state_prompt += "\n- FOLD"
        if actions.get('CALL', {}).get('available', False):
            state_prompt += "\n- CALL"
        if actions.get('CHECK', {}).get('available', False):
            state_prompt += "\n- CHECK"
        if actions.get('R'):
            state_prompt += f"\n- RAISE options: {[opt['value'] for opt in actions['R']]}"
        if actions.get('B'):
            state_prompt += f"\n- BET options: {[opt['value'] for opt in actions['B']]}"
            
        return state_prompt
        
    def get_decision(self, table_state: Dict, hand_history) -> Dict:
        """Get a decision from Claude based on the current table state and hand history"""
        prompt = self.format_game_state(table_state, hand_history)
        
        # Print debug info
        print("\nSending prompt to Claude:")
        print(prompt)
        
        system_prompt = """You are a professional poker strategy advisor for heads-up no-limit hold'em. Analyze the given poker situation and recommend the best action to take.

IMPORTANT: The input contains a "Hand Analysis" section with pre-calculated information about current hand strength, pair rankings, flush draws, and straight draws. This analysis is mathematically accurate - trust it completely and do not try to recalculate or contradict these calculations.

For example, if the analysis says "Flush draw: No", do not suggest that we have a flush draw or backdoor flush draw.

When making your decision, consider:
1. The pre-flop context and how it affects ranges
2. Position (SB vs BB) advantage
3. The accurate hand analysis provided
4. Pot odds and implied odds
5. Stack-to-pot ratio
6. Board texture and how it connects with likely ranges
7. Betting history and its implications

Your response should be in JSON format with the following structure:
{
    "action": "FOLD/CALL/CHECK/RAISE/BET",
    "amount": null or number (for raise/bet),
    "reasoning": "concise explanation of the decision focusing on why this is the best play in this specific spot"
}"""

        try:
            model = os.environ.get("CLAUDE_MODEL", "claude-3-sonnet-20240229")
            response = self.client.messages.create(
                model=model,
                max_tokens=1000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            
            # Parse the response content from Claude
            content = response.content[0].text
            
            # Extract JSON from possible markdown code blocks
            if "```json" in content:
                json_text = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_text = content.split("```")[1].split("```")[0].strip()
            else:
                json_text = content.strip()
                
            decision = json.loads(json_text)
            
            # Match the decision with available actions
            return self._match_decision_with_available_actions(decision, table_state)
            
        except Exception as e:
            print(f"Error getting decision from Claude: {e}")
            return {"action": "FOLD", "amount": None, "reasoning": "Error occurred with Claude API, defaulting to fold"}
    
    def _match_decision_with_available_actions(self, decision: Dict, table_state: Dict) -> Dict:
        """Match the AI decision with the available buttons on screen"""
        action_type = decision["action"]
        available_actions = table_state["available_actions"]
        
        # Handle simple actions (FOLD, CALL, CHECK)
        if action_type in ["FOLD", "CALL", "CHECK"]:
            if available_actions.get(action_type, {}).get("available", False):
                decision["position"] = available_actions[action_type]["position"]
                return decision
        
        # Handle RAISE
        elif action_type == "RAISE" and available_actions.get("R"):
            target_amount = decision["amount"]
            # Find closest available raise option
            closest_option = min(available_actions["R"], 
                                key=lambda x: abs(x["value"] - target_amount))
            decision["amount"] = closest_option["value"]
            decision["position"] = closest_option["position"]
            return decision
            
        # Handle BET
        elif action_type == "BET" and available_actions.get("B"):
            target_amount = decision["amount"]
            # Find closest available bet option
            closest_option = min(available_actions["B"], 
                                key=lambda x: abs(x["value"] - target_amount))
            decision["amount"] = closest_option["value"]
            decision["position"] = closest_option["position"]
            return decision
        
        # Default to fold if action not available
        print(f"Action {action_type} not available, defaulting to fold")
        if available_actions.get("FOLD", {}).get("available", False):
            return {
                "action": "FOLD",
                "amount": None,
                "position": available_actions["FOLD"]["position"],
                "reasoning": f"Original action ({action_type}) not available, defaulting to fold"
            }
        
        # If fold not available, check if we can check
        if available_actions.get("CHECK", {}).get("available", False):
            return {
                "action": "CHECK",
                "amount": None,
                "position": available_actions["CHECK"]["position"],
                "reasoning": f"Original action ({action_type}) not available, defaulting to check"
            }
            
        return {"action": "WAIT", "reasoning": "No valid action available"}