import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from ppadb.client import Client as AdbClient
from src.detector.action_button_detector import ActionButtonDetector
from src.detector.text_detector import TextDetector

def connect_device():
    adb = AdbClient(host="127.0.0.1", port=5037)
    devices = adb.devices()
    if not devices:
        raise Exception("No devices found")
    return devices[0]

def capture_screen(device):
    screenshot_data = device.screencap()
    nparr = np.frombuffer(screenshot_data, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

def visualize_detections(screen):
    # Initialize detectors
    action_detector = ActionButtonDetector('card_templates/action_templates')
    text_detector = TextDetector()
    
    # Create a copy for visualization
    debug_image = screen.copy()
    
    # Detect action buttons with lower threshold
    action_region = screen[1567:1904, 35:1046]  # Original action region
    
    # Draw action region boundary
    cv2.rectangle(debug_image, (35, 1567), (1046, 1904), (255, 0, 0), 2)
    cv2.putText(debug_image, "Action Region", (35, 1557), 
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
    
    # Detect buttons
    screen_white_text = action_detector.isolate_white_text(action_region)
    
    for action_type, template in action_detector.action_templates.items():
        # Use lower threshold for raise/bet buttons
        threshold = 0.8 if action_type in ['R', 'B'] else 0.8
        result = cv2.matchTemplate(screen_white_text, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        
        for pt in zip(*locations[::-1]):
            # Convert coordinates relative to full screen
            x = pt[0] + 35  # Add action region offset
            y = pt[1] + 1567
            
            # Draw button location
            cv2.circle(debug_image, (x, y), 5, (0, 255, 0), -1)
            cv2.putText(debug_image, action_type, (x + 10, y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Draw bet size extraction region
            if action_type in ['R', 'B']:
                x1 = x + 45   # x_offset
                y1 = y - 5   # y_offset
                x2 = x + 160  # x_offset + width
                y2 = y + 50   # y_offset + height
                
                cv2.rectangle(debug_image, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(debug_image, "Bet Size ROI", (x1, y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                # Extract and show detected value
                roi = screen[y1:y2, x1:x2]
                if roi.size > 0:  # Check if ROI is valid
                    value = text_detector.detect_value(roi)
                    cv2.putText(debug_image, f"Value: {value}", (x2 + 5, y), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    
    return debug_image

def main():
    device = connect_device()
    screen = capture_screen(device)
    
    # Visualize detections
    debug_image = visualize_detections(screen)
    
    # Save debug image
    cv2.imwrite('debug_detections.png', debug_image)
    
    # Display image (optional)
    cv2.imshow('Detections', debug_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()