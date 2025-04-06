import cv2
import os
import numpy as np
from typing import List, Optional
from src.models.card import Card
from src.detector.template_matcher import TemplateMatcher
from src.detector.text_detector import TextDetector
from src.config.regions import *
from src.detector.action_button_detector import ActionButtonDetector
from typing import List, Dict, Optional, Tuple

class PokerTableDetector:
    def __init__(self, template_matcher: TemplateMatcher):
        self.template_matcher = template_matcher
        self.text_detector = TextDetector()
        self.action_detector = ActionButtonDetector('card_templates/action_templates')


    def detect_card(self, roi: np.ndarray, is_hero: bool = False) -> Optional[Card]:
        best_rank = None
        best_rank_conf = 0
        best_suit = None
        best_suit_conf = 0

        rank_templates = (self.template_matcher.hero_rank_templates 
                        if is_hero 
                        else self.template_matcher.community_rank_templates)
        
        suit_templates = (self.template_matcher.hero_suit_templates 
                         if is_hero 
                         else self.template_matcher.community_suit_templates)

        # Match rank
        for rank, template in rank_templates.items():
            conf, _ = self.template_matcher.match_template(roi, template)
            if conf > best_rank_conf:
                best_rank_conf = conf
                best_rank = rank

        # Match suit
        for suit, template in suit_templates.items():
            conf, _ = self.template_matcher.match_template(roi, template,use_preprocessing=False)
            if conf > best_suit_conf:
                best_suit_conf = conf
                best_suit = suit

        if best_rank_conf > 0.6 and best_suit_conf > 0.9:
            return Card(best_rank, best_suit, min(best_rank_conf, best_suit_conf))
        return None
    
    def detect_button_position(self, screen: np.ndarray) -> dict:
        button_positions = {'hero': False, 'villain': False}
        
        # Load button template
        btn_template = cv2.imread(os.path.join(self.template_matcher.template_path, 'object_templates/btn.png'))
        
        for player, region in BUTTON_REGIONS.items():
            roi = screen[region['y1']:region['y2'], region['x1']:region['x2']]
            confidence, _ = self.template_matcher.match_template(roi, btn_template)
            button_positions[player] = confidence > 0.8
        
        return button_positions
    
    def detect_positions(self, button_positions: dict) -> dict:
        """Determine player positions based on button location"""
        positions = {'SB': None, 'BB': None}
        
        if button_positions['hero']:
            positions['SB'] = 'hero'
            positions['BB'] = 'villain'
        elif button_positions['villain']:
            positions['SB'] = 'villain'
            positions['BB'] = 'hero'
            
        return positions    
    
    def detect_hero_turn(self, screen: np.ndarray) -> bool:
        # Load hero turn template
        turn_template = cv2.imread(os.path.join(self.template_matcher.template_path,'object_templates/hero_turn.png'))
        
        roi = screen[HERO_TURN_REGION['y1']:HERO_TURN_REGION['y2'], 
                    HERO_TURN_REGION['x1']:HERO_TURN_REGION['x2']]
        
        confidence, _ = self.template_matcher.match_template(roi, turn_template)
        return confidence > 0.8
    
    def is_preflop(self, screen: np.ndarray) -> bool:
        """Determine if we're in preflop by checking for community cards"""
        for region in COMMUNITY_CARD_REGIONS[:3]:  # Check first 3 cards (flop)
            roi = screen[region['y1']:region['y2'], region['x1']:region['x2']]
            card = self.detect_card(roi, is_hero=False)
            if card:
                return False
        return True
    
    def detect_street(self, community_cards: List[Card]) -> str:
        """Determine the current street based on number of community cards"""
        num_cards = len(community_cards)
        
        if num_cards == 0:
            return "Preflop"
        elif num_cards == 3:
            return "Flop"
        elif num_cards == 4:
            return "Turn"
        elif num_cards == 5:
            return "River"
        else:
            return "Unknown"

    def detect_pot_size(self, screen: np.ndarray) -> float:
        """Detect pot size using appropriate region based on street"""
        is_preflop_street = self.is_preflop(screen)
        
        # Try preflop region first if we're preflop
        if is_preflop_street:
            preflop_roi = screen[POT_REGION_PREFLOP['y1']:POT_REGION_PREFLOP['y2'], 
                               POT_REGION_PREFLOP['x1']:POT_REGION_PREFLOP['x2']]
            pot_size = self.text_detector.detect_value(preflop_roi)
            if pot_size > 0:
                return pot_size

        # Try postflop region
        postflop_roi = screen[POT_REGION_POSTFLOP['y1']:POT_REGION_POSTFLOP['y2'], 
                            POT_REGION_POSTFLOP['x1']:POT_REGION_POSTFLOP['x2']]
        return self.text_detector.detect_value(postflop_roi)
    
    def process_action_detections(self, screen: np.ndarray, detections: List[Dict]) -> Dict:
        """
        Process raw action button detections into structured format
        
        Args:
            screen (np.ndarray): The full screenshot
            detections (List[Dict]): List of detected actions
        """
        available_actions = {
            'FOLD': {'available': False, 'position': None},
            'CALL': {'available': False, 'position': None},
            'CHECK': {'available': False, 'position': None},
            'R': [], # List of dicts: {'value': number, 'position': (x, y)}
            'B': []
        }

        # Group similar detections by position (within 5 pixels)
        processed_positions = set()
        
        for detection in detections:
            action_type = detection['type']
            pos = detection['position']
            
            # Skip if we already processed a similar position
            skip = False
            for processed_pos in processed_positions:
                if (abs(pos[0] - processed_pos[0]) < 5 and 
                    abs(pos[1] - processed_pos[1]) < 5):
                    skip = True
                    break
            if skip:
                continue
                
            processed_positions.add(pos)
            
            if action_type in ['FOLD', 'CALL', 'CHECK']:
                available_actions[action_type]['available'] = True
                available_actions[action_type]['position'] = pos
            elif action_type in ['R', 'B']:
                # Extract value from the button region
                value = self.extract_action_value(screen, pos)
                if value > 0:
                    available_actions[action_type].append({'value': value, 'position': pos})

        return available_actions

    def extract_action_value(self, screen: np.ndarray, position: Tuple[int, int], debug: bool = False) -> float:
        """
        Extract numerical value from B/R buttons with optimized offsets
        """
        x, y = position
        
        # Update to the optimized offset values
        value_roi_x1 = x + 45   # x_offset
        value_roi_y1 = y - 5    # y_offset
        value_roi_x2 = x + 160  # x_offset + width
        value_roi_y2 = y + 50   # y_offset + height
        
        value_roi = screen[value_roi_y1:value_roi_y2, value_roi_x1:value_roi_x2]
        
        if debug:
            cv2.imwrite(f'debug_value_roi_{x}_{y}.png', value_roi)
        
        return self.text_detector.detect_value(value_roi)

    def detect_table_state(self, screen: np.ndarray):
        # Detect hero cards
        hero_cards = []
        for region in HERO_CARD_REGIONS:
            roi = screen[region['y1']:region['y2'], region['x1']:region['x2']]
            card = self.detect_card(roi, is_hero=True)
            if card:
                hero_cards.append(card)

        # Detect community cards
        community_cards = []
        for region in COMMUNITY_CARD_REGIONS:
            roi = screen[region['y1']:region['y2'], region['x1']:region['x2']]
            card = self.detect_card(roi, is_hero=False)
            if card:
                community_cards.append(card)

        # Detect stacks
        stacks = {}
        for player, region in STACK_REGIONS.items():
            roi = screen[region['y1']:region['y2'], region['x1']:region['x2']]
            stacks[player] = self.text_detector.detect_value(roi)

        # Detect bets
        bets = {}
        for player, region in BET_REGIONS.items():
            roi = screen[region['y1']:region['y2'], region['x1']:region['x2']]
            bets[player] = self.text_detector.detect_value(roi)

        # Detect pot
        pot_size = self.detect_pot_size(screen)

        # Detect button positions and determine player positions
        button_positions = self.detect_button_position(screen)
        positions = self.detect_positions(button_positions)
        
        # Determine street
        street = self.detect_street(community_cards)
        
        # Add hero turn detection
        is_hero_turn = self.detect_hero_turn(screen)  

         # Add action button detection
        action_detections = self.action_detector.detect_action_buttons(screen)
        available_actions = self.process_action_detections(screen, action_detections)  # Pass screen here

        # Add preflop pot type detection
        preflop_pot_type = self.template_matcher.detect_preflop_pot_type(screen)
        
        # Create mapping between pot types and their meanings
        pot_type_descriptions = {
            '2_bet_pot': "SB open raise -> BB call",
            '3_bet_pot': "SB open raise -> BB 3-bet -> SB call",
            '4_bet_pot': "SB open raise -> BB 3-bet -> SB 4-bet -> BB call"
        }
        
        pot_type_description = pot_type_descriptions.get(preflop_pot_type, "Unknown pot type")
            

        return {
            'hero_cards': hero_cards,
            'community_cards': community_cards,
            'stacks': stacks,
            'bets': bets,
            'pot_size': pot_size,
            'button_positions': button_positions,
            'positions': positions,
            'is_hero_turn': is_hero_turn,
            'street': street,
            'available_actions': available_actions,
            'preflop_pot_type': preflop_pot_type,
            'pot_type_description': pot_type_description
        }
    