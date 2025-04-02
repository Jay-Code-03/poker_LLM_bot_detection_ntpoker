# src/detector/action_button_detector.py

import os
import cv2
import numpy as np

class ActionButtonDetector:
    def __init__(self, template_path: str):
        """
        Initialize the ActionButtonDetector
        
        Args:
            template_path (str): Path to the directory containing action button templates
        """
        self.template_path = template_path
        self.action_templates = {}
        self.load_action_templates()
    
    def isolate_white_text(self, image):
        """Extract white text from image"""
        if image is None:
            raise ValueError("Image is None - failed to load image")
            
        # Convert to grayscale first
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Threshold to get white text
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        return binary

    def load_action_templates(self):
        """Load all action button templates and process them to extract white text"""
        action_types = ['FOLD', 'CALL', 'CHECK', 'R', 'B']
        for action in action_types:
            template_path = os.path.join(self.template_path, f'action_{action.lower()}.png')
            if os.path.exists(template_path):
                template = cv2.imread(template_path)
                if template is not None:
                    # Extract white text from template
                    white_text = self.isolate_white_text(template)
                    self.action_templates[action] = white_text
                else:
                    print(f"Failed to load template: {template_path}")
            else:
                print(f"Template file does not exist: {template_path}")

    def detect_action_buttons(self, screen: np.ndarray, debug=False) -> list:
        """
        Detect all action buttons in the screen
        """
        # Update action region coordinates
        action_region = screen[1567:1904, 35:1046]
        
        # Extract white text from screen
        screen_white_text = self.isolate_white_text(action_region)
        
        detected_actions = []
        
        for action_type, template in self.action_templates.items():
            # Use consistent threshold
            threshold = 0.8
            result = cv2.matchTemplate(screen_white_text, template, cv2.TM_CCOEFF_NORMED)
            locations = np.where(result >= threshold)
            
            for pt in zip(*locations[::-1]):
                # Add action region offset to coordinates
                adjusted_x = pt[0] + 35
                adjusted_y = pt[1] + 1567
                
                detected_actions.append({
                    'type': action_type,
                    'position': (adjusted_x, adjusted_y),
                    'confidence': result[pt[1]][pt[0]]
                })
        
        detected_actions.sort(key=lambda x: x['position'][0])
        return detected_actions