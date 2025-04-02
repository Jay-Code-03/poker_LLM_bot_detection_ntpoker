# src/engine/decision_engine.py
from openai import OpenAI
from typing import Dict, List
import json

class DecisionEngine:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        
    def format_game_state(self, table_state: Dict) -> str:
        """Format the table state into a clear prompt for the LLM"""
        hero_cards = [f"{c.rank}{c.suit}" for c in table_state['hero_cards']]
        community_cards = [f"{c.rank}{c.suit}" for c in table_state['community_cards']]
        
        state_prompt = f"""
Current poker situation:
Hero cards: {', '.join(hero_cards)}
Community cards: {', '.join(community_cards)}
Pot size: ${table_state['pot_size']:.2f}
Hero stack: ${table_state['stacks']['hero']:.2f}
Villain stack: ${table_state['stacks']['villain']:.2f}
Hero bet: ${table_state['bets']['hero']:.2f}
Villain bet: ${table_state['bets']['villain']:.2f}
Button positions: {table_state['button_positions']}
Street: {"Preflop" if table_state['is_preflop'] else "Postflop"}

Available actions:"""
        
        actions = table_state['available_actions']
        if actions['FOLD']:
            state_prompt += "\n- FOLD"
        if actions['CALL']:
            state_prompt += "\n- CALL"
        if actions['CHECK']:
            state_prompt += "\n- CHECK"
        if actions['R']:
            state_prompt += f"\n- RAISE options: {actions['R']}"
        if actions['B']:
            state_prompt += f"\n- BET options: {actions['B']}"
            
        return state_prompt
        
    def get_decision(self, table_state: Dict) -> Dict:
        """Get a decision from the LLM based on the current table state"""
        prompt = self.format_game_state(table_state)
        
        system_prompt = """You are a poker strategy advisor. Analyze the given poker situation and recommend the best action to take.
Your response should be in JSON format with the following structure:
{
    "action": "FOLD/CALL/CHECK/RAISE/BET",
    "amount": null or number (for raise/bet),
    "reasoning": "brief explanation of the decision"
}
Consider position, pot odds, and stack sizes in your analysis."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={ "type": "json_object" }
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Error getting decision: {e}")
            return {"action": "FOLD", "amount": None, "reasoning": "Error occurred, defaulting to fold"}