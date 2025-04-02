import cv2
import numpy as np
from ppadb.client import Client as AdbClient
from dataclasses import dataclass
from typing import List, Tuple, Dict
import os
import time
import pytesseract
from PIL import Image

@dataclass
class Card:
    rank: str
    suit: str
    confidence: float

class PokerCardDetector:
    def __init__(self):
        # Initialize templates
        self.hero_rank_templates = {}
        self.hero_suit_templates = {}
        self.community_rank_templates = {}
        self.community_suit_templates = {}
        self.template_path = 'card_templates'
        self.load_templates()

        self.hero_card_regions = [
            {'x1': 464, 'y1': 1289, 'x2': 541, 'y2': 1400},  # First hero card
            {'x1': 540, 'y1': 1291, 'x2': 616, 'y2': 1398}   # Second hero card
        ]
        
        self.community_card_regions = [
            {'x1': 299, 'y1': 870, 'x2': 390, 'y2': 1022},  # Flop 1
            {'x1': 399, 'y1': 871, 'x2': 485, 'y2': 1019},  # Flop 2
            {'x1': 496, 'y1': 873, 'x2': 586, 'y2': 1015},  # Flop 3
            {'x1': 592, 'y1': 871, 'x2': 682, 'y2': 1023},  # Turn
            {'x1': 688, 'y1': 870, 'x2': 780, 'y2': 1019}   # River
        ]

        self.villain_stack_region = {'x1': 465, 'y1': 536, 'x2': 615, 'y2': 587}
        self.hero_stack_region = {'x1': 466, 'y1': 1477, 'x2': 615, 'y2': 1519}

        self.villain_bet_region = {'x1': 449, 'y1': 663, 'x2': 650, 'y2': 717}
        self.hero_bet_region = {'x1': 449, 'y1': 1216, 'x2': 652, 'y2': 1270}

        self.villain_button_region = {'x1': 644, 'y1': 564, 'x2': 702, 'y2': 623}
        self.hero_button_region = {'x1': 632, 'y1': 1347, 'x2': 688, 'y2': 1406}

        self.pot_region = {'x1': 403, 'y1': 802, 'x2': 562, 'y2': 866}

        # Initialize ADB
        # Need to use termainal: adb connect 127.0.0.1:5555 before start
        self.adb = AdbClient(host="127.0.0.1", port=5037)
        self.device = self.connect_to_device()

    def connect_to_device(self):
        devices = self.adb.devices()
        if not devices:
            raise Exception("No devices found. Make sure your emulator is running.")
        return devices[0]

    def load_templates(self):
        """Load all template images from the template directory"""
        # Load hero rank templates
        hero_rank_path = os.path.join(self.template_path, 'ranks_hero')
        for filename in os.listdir(hero_rank_path):
            if filename.endswith('.png'):
                rank = filename.split('.')[0]
                template = cv2.imread(os.path.join(hero_rank_path, filename))
                if template is not None:
                    self.hero_rank_templates[rank] = template

        # Load hero suit templates
        hero_suit_path = os.path.join(self.template_path, 'suits_hero')
        for filename in os.listdir(hero_suit_path):
            if filename.endswith('.png'):
                suit = filename.split('.')[0]
                template = cv2.imread(os.path.join(hero_suit_path, filename))
                if template is not None:
                    self.hero_suit_templates[suit] = template

        # Load community rank templates
        community_rank_path = os.path.join(self.template_path, 'ranks_community')
        for filename in os.listdir(community_rank_path):
            if filename.endswith('.png'):
                rank = filename.split('.')[0]
                template = cv2.imread(os.path.join(community_rank_path, filename))
                if template is not None:
                    self.community_rank_templates[rank] = template

        # Load community suit templates
        community_suit_path = os.path.join(self.template_path, 'suits_community')
        for filename in os.listdir(community_suit_path):
            if filename.endswith('.png'):
                suit = filename.split('.')[0]
                template = cv2.imread(os.path.join(community_suit_path, filename))
                if template is not None:
                    self.community_suit_templates[suit] = template

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for template matching"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Clean up noise
        kernel = np.ones((3,3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return binary
    
    
    
    def preprocess_text_region(self, roi: np.ndarray) -> np.ndarray:
        """Preprocess region of interest for OCR"""
        # Convert to grayscale
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding to get black text on white background
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        
        # Increase image size to improve OCR accuracy
        scaled = cv2.resize(binary, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # Optional: Apply some noise reduction
        denoised = cv2.fastNlMeansDenoising(scaled)
    
        return denoised
    
    def preprocess_text_region_for_black_background(self, roi: np.ndarray) -> np.ndarray:
        """Preprocess region of interest for OCR - optimized for white text on dark background"""
        # Convert to grayscale
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Increase contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
        
        # Invert image (makes white text on black background -> black text on white background)
        gray = cv2.bitwise_not(gray)
        
        # Apply adaptive thresholding
        binary = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,  # block size
            2    # constant subtracted from mean
        )
        
        # Scale up image
        scaled = cv2.resize(binary, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # Optional: Reduce noise
        denoised = cv2.fastNlMeansDenoising(scaled)
        
        return denoised
    
    def extract_number(self, text: str) -> float:
        """Extract numerical value from text string"""
        # Remove all non-numeric characters except decimal points
        numbers = ''.join(c for c in text if c.isdigit() or c == '.')
        try:
            # Convert to float
            return float(numbers)
        except ValueError:
            return 0.0
        
    def detect_stack_sizes(self, screen: np.ndarray) -> dict:
        """Detect hero and villain stack sizes"""
        stacks = {}
        
        # Process hero stack
        hero_roi = screen[
            self.hero_stack_region['y1']:self.hero_stack_region['y2'],
            self.hero_stack_region['x1']:self.hero_stack_region['x2']
        ]
        hero_processed = self.preprocess_text_region(hero_roi)
        hero_text = pytesseract.image_to_string(hero_processed, config='--psm 7 digits')
        stacks['hero'] = self.extract_number(hero_text)
        
        # Process villain stack
        villain_roi = screen[
            self.villain_stack_region['y1']:self.villain_stack_region['y2'],
            self.villain_stack_region['x1']:self.villain_stack_region['x2']
        ]
        villain_processed = self.preprocess_text_region(villain_roi)
        villain_text = pytesseract.image_to_string(villain_processed, config='--psm 7 digits')
        stacks['villain'] = self.extract_number(villain_text)
        
        return stacks

    def detect_bets(self, screen: np.ndarray) -> dict:
        """Detect hero and villain bets"""
        bets = {}
        
        # Process hero bet
        hero_roi = screen[
            self.hero_bet_region['y1']:self.hero_bet_region['y2'],
            self.hero_bet_region['x1']:self.hero_bet_region['x2']
        ]
        hero_processed = self.preprocess_text_region(hero_roi)
        hero_text = pytesseract.image_to_string(hero_processed, config='--psm 7 digits')
        bets['hero'] = self.extract_number(hero_text)
        
        # Process villain bet
        villain_roi = screen[
            self.villain_bet_region['y1']:self.villain_bet_region['y2'],
            self.villain_bet_region['x1']:self.villain_bet_region['x2']
        ]
        villain_processed = self.preprocess_text_region(villain_roi)
        villain_text = pytesseract.image_to_string(villain_processed, config='--psm 7 digits')
        bets['villain'] = self.extract_number(villain_text)
        
        return bets

    def detect_pot(self, screen: np.ndarray) -> float:
        """Detect pot size"""
        pot_roi = screen[
            self.pot_region['y1']:self.pot_region['y2'],
            self.pot_region['x1']:self.pot_region['x2']
        ]
        pot_processed = self.preprocess_text_region(pot_roi)
        pot_text = pytesseract.image_to_string(pot_processed, config='--psm 7 digits')
        return self.extract_number(pot_text)

    def match_template(self, image: np.ndarray, template: np.ndarray) -> Tuple[float, Tuple[int, int]]:
        """Perform template matching and return best match"""
        # Preprocess both images
        processed_image = self.preprocess_image(image)
        processed_template = self.preprocess_image(template)
        
        # Perform template matching
        result = cv2.matchTemplate(processed_image, processed_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        return max_val, max_loc
    
    def match_template_suit(self, image: np.ndarray, template: np.ndarray) -> Tuple[float, Tuple[int, int]]:
        """Perform template matching and return best match"""
        # Preprocess both images
        #processed_image = self.preprocess_image(image)
        #processed_template = self.preprocess_image(template)
        
        # Perform template matching
        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        
        return max_val, max_loc
    

    def detect_card(self, roi: np.ndarray, is_hero: bool = False) -> Card:
        """Detect rank and suit in a card region"""
        best_rank = None
        best_rank_conf = 0
        best_suit = None
        best_suit_conf = 0

        # Select appropriate templates based on card type
        rank_templates = self.hero_rank_templates if is_hero else self.community_rank_templates
        suit_templates = self.hero_suit_templates if is_hero else self.community_suit_templates

        # Match rank
        for rank, template in rank_templates.items():
            conf, _ = self.match_template(roi, template)
            if conf > best_rank_conf:
                best_rank_conf = conf
                best_rank = rank

        # Match suit
        for suit, template in suit_templates.items():
            conf, _ = self.match_template_suit(roi, template)
            if conf > best_suit_conf:
                best_suit_conf = conf
                best_suit = suit

        if best_rank_conf > 0.6 and best_suit_conf > 0.9:
            return Card(best_rank, best_suit, min(best_rank_conf, best_suit_conf))
        return None
    

    def capture_screen(self) -> np.ndarray:
        """Capture screenshot from device"""
        screenshot_data = self.device.screencap()
        nparr = np.frombuffer(screenshot_data, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    def find_coordinates(self):
        """Helper function to find card coordinates"""
        # Capture screen
        screen = self.capture_screen()
        
        # Save the screenshot
        cv2.imwrite("poker_screenshot.png", screen)
        
        # Create a window to display the image
        window_name = 'Card Coordinate Finder'
        cv2.namedWindow(window_name)
        
        def mouse_callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                print(f"Clicked coordinates: x={x}, y={y}")
        
        cv2.setMouseCallback(window_name, mouse_callback)
        
        while True:
            # Display the image with a grid
            display_img = screen.copy()
            height, width = screen.shape[:2]
            
            # Draw grid lines every 50 pixels
            for x in range(0, width, 50):
                cv2.line(display_img, (x, 0), (x, height), (0, 255, 0), 1)
                # Add coordinate labels
                cv2.putText(display_img, str(x), (x, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
            for y in range(0, height, 50):
                cv2.line(display_img, (0, y), (width, y), (0, 255, 0), 1)
                # Add coordinate labels
                cv2.putText(display_img, str(y), (5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            
            cv2.imshow(window_name, display_img)
            
            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cv2.destroyAllWindows()

    def find_coordinates_scaling(self):
        """Helper function to find card coordinates with resizable window"""
        # Capture screen
        screen = self.capture_screen()
        
        # Save the original screenshot
        cv2.imwrite("poker_screenshot.png", screen)
        
        # Create a resizable window
        window_name = 'Card Coordinate Finder (Press "q" to quit)'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        # Set initial window size to 800x600 or another comfortable size
        cv2.resizeWindow(window_name, 800, 600)
        
        # Keep track of the scale factor
        original_height, original_width = screen.shape[:2]
        
        def mouse_callback(event, x, y, flags, param):
            if event == cv2.EVENT_LBUTTONDOWN:
                # Get current window size
                window_width = cv2.getWindowImageRect(window_name)[2]
                window_height = cv2.getWindowImageRect(window_name)[3]
                
                # Calculate scale factors
                scale_x = original_width / window_width
                scale_y = original_height / window_height
                
                # Convert clicked coordinates back to original image coordinates
                original_x = int(x * scale_x)
                original_y = int(y * scale_y)
                
                print(f"Clicked coordinates in original image: x={original_x}, y={original_y}")
        
        cv2.setMouseCallback(window_name, mouse_callback)
        
        while True:
            # Get current window size
            window_rect = cv2.getWindowImageRect(window_name)
            if window_rect is not None:
                window_width = window_rect[2]
                window_height = window_rect[3]
                
                # Create display image with grid
                display_img = screen.copy()
                
                # Draw grid lines every 50 pixels
                for x in range(0, original_width, 50):
                    cv2.line(display_img, (x, 0), (x, original_height), (0, 255, 0), 1)
                    cv2.putText(display_img, str(x), (x, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    
                for y in range(0, original_height, 50):
                    cv2.line(display_img, (0, y), (0, original_height), (0, 255, 0), 1)
                    cv2.putText(display_img, str(y), (5, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                # Resize display image to fit window
                display_img_resized = cv2.resize(display_img, (window_width, window_height))
                
                cv2.imshow(window_name, display_img_resized)
            
            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cv2.destroyAllWindows()


    def run_detection(self):
        """Main detection loop"""

        while True:
            # Capture screen
            screen = self.capture_screen()
            
            # Detect hero cards
            hero_cards = []
            for region in self.hero_card_regions:
                roi = screen[region['y1']:region['y2'], region['x1']:region['x2']]
                card = self.detect_card(roi, is_hero=True)
                if card:
                    hero_cards.append(card)

            # Detect community cards
            community_cards = []
            for region in self.community_card_regions:
                roi = screen[region['y1']:region['y2'], region['x1']:region['x2']]
                card = self.detect_card(roi, is_hero=False)
                if card:
                    community_cards.append(card)

            # Detect stacks, bets and pot
            stacks = self.detect_stack_sizes(screen)
            bets = self.detect_bets(screen)
            pot_size = self.detect_pot(screen)

            # Print results
            print("\n=== Table State ===")
            print("Hero cards:", [f"{c.rank}{c.suit}" for c in hero_cards])
            print("Community cards:", [f"{c.rank}{c.suit}" for c in community_cards])
            print(f"Hero stack: ${stacks['hero']:.2f}")
            print(f"Villain stack: ${stacks['villain']:.2f}")
            print(f"Hero bet: ${bets['hero']:.2f}")
            print(f"Villain bet: ${bets['villain']:.2f}")
            print(f"Pot size: ${pot_size:.2f}")
            print("================\n")
            
            time.sleep(3)  # Add delay to prevent excessive CPU usage

def main():
    detector = PokerCardDetector()

    detector.find_coordinates()
    #detector.run_detection()

if __name__ == "__main__":
    main()