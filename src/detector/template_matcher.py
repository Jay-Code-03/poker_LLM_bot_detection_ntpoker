import cv2
import numpy as np
import os
from typing import Dict, Tuple

class TemplateMatcher:
    def __init__(self, template_path: str):
        self.template_path = template_path
        self.hero_rank_templates = {}
        self.hero_suit_templates = {}
        self.community_rank_templates = {}
        self.community_suit_templates = {}
        self.load_templates()

    def load_templates(self):
        """Load all template images from the template directory"""
        # Load hero rank templates
        self._load_templates('ranks_hero', self.hero_rank_templates)
        self._load_templates('suits_hero', self.hero_suit_templates)
        self._load_templates('ranks_community', self.community_rank_templates)
        self._load_templates('suits_community', self.community_suit_templates)

    def _load_templates(self, subfolder: str, template_dict: Dict):
        path = os.path.join(self.template_path, subfolder)
        for filename in os.listdir(path):
            if filename.endswith('.png'):
                key = filename.split('.')[0]
                template = cv2.imread(os.path.join(path, filename))
                if template is not None:
                    template_dict[key] = template

    def match_template(self, image: np.ndarray, template: np.ndarray, 
                      use_preprocessing: bool = True) -> Tuple[float, Tuple[int, int]]:
        if use_preprocessing:
            processed_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            processed_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        else:
            processed_image = image
            processed_template = template

        result = cv2.matchTemplate(processed_image, processed_template, 
                                 cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        return max_val, max_loc
    
    def detect_next_hand_button(self, screen: np.ndarray) -> Tuple[bool, Tuple[int, int]]:
        """
        Detect the 'Next Hand' button on the screen.
        
        Args:
            screen (np.ndarray): The current screen image
            
        Returns:
            Tuple[bool, Tuple[int, int]]: (is_detected, (x, y) position)
        """
        next_hand_template = cv2.imread(os.path.join(self.template_path, 'object_templates/next_hand.png'))
        
        if next_hand_template is None:
            print("Warning: Next Hand template could not be loaded")
            return False, (0, 0)
        
        # Look for the button in the bottom half of the screen where it's likely to appear
        height, width = screen.shape[:2]
        search_area = screen[height//2:, :]
        
        # Match the template
        result = cv2.matchTemplate(search_area, next_hand_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        # Adjust position back to full screen coordinates
        if max_val > 0.7:  # Threshold can be adjusted
            x = max_loc[0] + next_hand_template.shape[1]//2  # Center of button X
            y = max_loc[1] + height//2 + next_hand_template.shape[0]//2  # Center of button Y
            return True, (x, y)
        
        return False, (0, 0)
    
    # Add to src/detector/template_matcher.py
    def detect_preflop_pot_type(self, screen: np.ndarray) -> str:
        """
        Detect preflop scenario based on templates in the specified region.
        
        Args:
            screen (np.ndarray): The full screenshot
            
        Returns:
            str: Detected scenario ('2_bet_pot', '3_bet_pot', '4_bet_pot', or 'unknown')
        """
        # Define the region where preflop scenario indicators appear
        preflop_region = screen[1100:1200, 400:700]
        
        # Define possible scenarios and their corresponding template files
        scenarios = ['2_bet_pot', '3_bet_pot', '4_bet_pot']
        
        best_match = None
        best_confidence = 0.0
        
        for scenario in scenarios:
            template_path = os.path.join(self.template_path, f'preflop_templates/{scenario}.png')
            if not os.path.exists(template_path):
                print(f"Warning: Template {template_path} does not exist")
                continue
                
            template = cv2.imread(template_path)
            if template is None:
                print(f"Warning: Failed to load template {template_path}")
                continue
            
            confidence, _ = self.match_template(preflop_region, template)
            
            if confidence > best_confidence and confidence > 0.7:  # Threshold can be adjusted
                best_confidence = confidence
                best_match = scenario
        
        return best_match if best_match else "unknown"