# src/engine/claude_post_flop_engine.py
from anthropic import Anthropic
from typing import Dict, List
import json
import os
from src.utils.hand_analyzer import HandAnalyzer  # Import the new HandAnalyzer
from src.utils.equity_calculator import EquityCalculator

class ClaudePostFlopEngine:
    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        self.client = Anthropic(api_key=api_key)
        self.hand_analyzer = HandAnalyzer()  # Initialize the hand analyzer
        self.equity_calculator = EquityCalculator()

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

        # Calculate effective pot size before current bets
        hero_bet = table_state['bets']['hero']
        villain_bet = table_state['bets']['villain']
        current_bets_total = hero_bet + villain_bet
        pot_before_bets = table_state['pot_size'] - current_bets_total
        
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


        # Add equity analysis section
        equity_info = ""
        if community_cards:  # Only calculate if we have community cards
            print(f"Calling equity calculator with {len(community_cards)} community cards")
            try:
                equity_result = self.equity_calculator.calculate_equity(
                    hero_cards=hero_cards,
                    board_cards=community_cards,
                    preflop_pot_type=hand_history.preflop_pot_type,
                    hand_history=hand_history,
                    iterations=5000  # Adjust based on performance needs
                )
                
                if "error" not in equity_result:
                    equity_percentage = equity_result["equity"] * 100
                    equity_info = "\n## Equity Analysis (Mathematically Verified):\n"
                    equity_info += f"- Hero equity vs villain range: {equity_percentage:.2f}%\n"
                    equity_info += f"- Villain range: {equity_result['range_description']}\n"
                    equity_info += f"- Based on {equity_result['iterations']} Monte Carlo simulations\n"
                    
                    # Add decision guidance based on equity
                    equity_info += "\nEquity-based decision guidance:\n"
                    if equity_percentage > 60:
                        equity_info += "- Strong equity (>60%) suggests strong value range\n"
                    elif equity_percentage > 45:
                        equity_info += "- Good equity (45-60%) suggests middle strength range\n"
                    elif equity_percentage > 35:
                        equity_info += "- Marginal equity (35-45%) suggests marginal range\n"
                    else:
                        equity_info += "- Weak equity (<35%) suggests weak range\n"
                    
                    # Print the equity info to console for verification
                    print("\n=== EQUITY INFO SENT TO CLAUDE ===")
                    print(equity_info)
                    print("=================================\n")
                else:
                    print(f"Error in equity calculation: {equity_result['error']}")
            except Exception as e:
                import traceback
                print(f"Exception during equity calculation: {e}")
                print(traceback.format_exc())
    
        state_prompt = f"""
# Current Poker Situation (Heads-Up No-Limit Hold'em)
In Heads-Up No-Limit Hold'em, the pre-flop action is SB takes the action first, followed by BB, then back to SB if BB choose to raise.
When goes to post-flop(Flop,Turn, River), the action is always BB take action first, followed by SB, each post-flop street is the same, start from the BB.


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
{equity_info}

## Stack and Pot Information:
- Pot before current bets: ${pot_before_bets:.2f}
- Current pot total: ${table_state['pot_size']:.2f} (includes all bets)
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

"Equity Analysis" section with rough equity calculations against villain's pre-flop range. It's most useful on the flop, on the turn and river, the range and equity would change due to the different actions.

Guidelines for equity-based decisions:
- If your equity is > 60%, you typically have a strong hand that can build a pot using betting or raising
- If your equity is between 45-60%, you have a medium-strong hand that can value bet thinly or call
- If your equity is between 35-45%, you have a marginal hand that should check/call or sometimes bet as a bluff
- If your equity is < 35%, you have a weak hand that should often check/fold or sometimes bluff

When SPR is lower than 4, using bet size lower than 35% on the flop in default, since if we have a value hand want to get as much value as possible, even we bet small on the flop, we can still get all the money in easily. If we have a bluffing hand, we don't want to bet too much and commit to the pot.

Review the previous action reasonings in the hand history. Maintain 
strategic consistency with prior decisions unless the board texture or betting 
patterns have significantly changed. Explain how your current decision relates to 
or differs from previous reasoning on earlier streets.

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