import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from src.utils.device_connector import DeviceConnector
from src.utils.image_preprocessing import ImagePreprocessor
from src.detector.text_detector import TextDetector
from src.config.regions import STACK_REGIONS, BET_REGIONS, POT_REGION

class OCRDebugger:
    def __init__(self):
        self.device = DeviceConnector.connect_device()
        self.text_detector = TextDetector()

    def capture_screen(self):
        screenshot_data = self.device.screencap()
        nparr = np.frombuffer(screenshot_data, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def debug_region(self, screen, region, name):
        # Extract region
        roi = screen[region['y1']:region['y2'], region['x1']:region['x2']]
        
        # Save original ROI
        cv2.imwrite(f"debug_images/{name}_original.png", roi)
        
        # Get preprocessed image
        preprocessed = ImagePreprocessor.preprocess_for_ocr(roi)
        cv2.imwrite(f"debug_images/{name}_preprocessed.png", preprocessed)
        
        # Get OCR result
        text = self.text_detector.detect_text(roi)
        value = self.text_detector.extract_number(text)
        
        return {
            'text': text,
            'value': value,
            'roi': roi,
            'preprocessed': preprocessed
        }

    def run_debug(self):
        # Create debug_images directory if it doesn't exist
        os.makedirs("debug_images", exist_ok=True)
        
        # Capture screen
        screen = self.capture_screen()
        cv2.imwrite("debug_images/full_screen.png", screen)
        
        # Debug each region
        regions_to_check = {
            'hero_stack': STACK_REGIONS['hero'],
            'villain_stack': STACK_REGIONS['villain'],
            'hero_bet': BET_REGIONS['hero'],
            'villain_bet': BET_REGIONS['villain'],
            'pot': POT_REGION
        }
        
        results = {}
        for name, region in regions_to_check.items():
            results[name] = self.debug_region(screen, region, name)
            
        # Print results
        print("\n=== OCR Debug Results ===")
        for name, result in results.items():
            print(f"\n{name.upper()}:")
            print(f"Raw OCR text: '{result['text']}'")
            print(f"Extracted value: {result['value']}")
            
        print("\nDebug images have been saved to the 'debug_images' directory")
        print("Check the images to see the exact regions being captured and their preprocessing")

def main():
    debugger = OCRDebugger()
    debugger.run_debug()

if __name__ == "__main__":
    main()