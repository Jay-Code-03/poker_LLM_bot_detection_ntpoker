# debug_action_detector.py
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from src.detector.action_button_detector import ActionButtonDetector

def debug_template_matching():
    # Get the absolute path to the project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # Set up paths
    template_dir = os.path.join(project_root, 'card_templates', 'action_templates')
    test_image_path = os.path.join(project_root, 'poker_screenshot.png')
    
    # Create detector
    detector = ActionButtonDetector(template_dir)
    
    # Load test image
    test_image = cv2.imread(test_image_path)
    if test_image is None:
        raise ValueError(f"Failed to load test image from {test_image_path}")
    
    # Detect buttons
    detected_actions = detector.detect_action_buttons(test_image)
    
    # Print results
    print("\nDetected actions:")
    for action in detected_actions:
        print(f"Type: {action['type']}, Position: {action['position']}, "
              f"Confidence: {action['confidence']:.2f}")

if __name__ == "__main__":
    try:
        debug_template_matching()
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()