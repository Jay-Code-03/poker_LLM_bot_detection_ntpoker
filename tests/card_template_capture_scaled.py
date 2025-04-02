import cv2
import numpy as np
from ppadb.client import Client as AdbClient
import os

class CardTemplateCapture:
    def __init__(self):
        # Create output directory if it doesn't exist
        self.output_dir = 'card_templates'
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # Initialize ADB connection
        self.adb = AdbClient(host="127.0.0.1", port=5037)
        self.devices = self.adb.devices()
        
        if not self.devices:
            raise Exception("No devices found. Make sure your emulator is running.")
        
        self.device = self.devices[0]
        
        # Initialize variables for region selection
        self.start_point = None
        self.end_point = None
        self.drawing = False
        self.current_image = None
        self.original_image = None
        self.template_count = 0
        
        # Set target display height (adjust this based on your screen)
        self.target_height = 1200
    
    def take_screenshot(self):
        """Take a screenshot and return both original and resized versions."""
        screenshot_data = self.device.screencap()
        nparr = np.frombuffer(screenshot_data, np.uint8)
        self.original_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Calculate scaling factor to fit screen height
        scale = self.target_height / self.original_image.shape[0]
        new_width = int(self.original_image.shape[1] * scale)
        
        # Resize image for display
        self.current_image = cv2.resize(self.original_image, (new_width, self.target_height))
        return self.current_image.copy()
    
    def get_scale_factor(self):
        """Calculate the scale factor between original and display images."""
        return self.original_image.shape[0] / self.current_image.shape[0]
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for selecting regions."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
        
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            temp_img = self.current_image.copy()
            cv2.rectangle(temp_img, self.start_point, (x, y), (0, 255, 0), 2)
            cv2.imshow('Capture Cards', temp_img)
        
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.end_point = (x, y)
            
            # Calculate rectangle coordinates on display image
            x1 = min(self.start_point[0], self.end_point[0])
            y1 = min(self.start_point[1], self.end_point[1])
            x2 = max(self.start_point[0], self.end_point[0])
            y2 = max(self.start_point[1], self.end_point[1])
            
            # Scale coordinates to original image size
            scale = self.get_scale_factor()
            orig_x1 = int(x1 * scale)
            orig_y1 = int(y1 * scale)
            orig_x2 = int(x2 * scale)
            orig_y2 = int(y2 * scale)
            
            # Extract and save the selected region from original image
            if (orig_x2 - orig_x1) > 0 and (orig_y2 - orig_y1) > 0:
                card = self.original_image[orig_y1:orig_y2, orig_x1:orig_x2]
                filename = os.path.join(self.output_dir, f'card_{self.template_count}.png')
                cv2.imwrite(filename, card)
                print(f"Saved {filename}")
                self.template_count += 1
    
    def capture_templates(self):
        """Main loop for capturing templates."""
        print("Instructions:")
        print("1. Click and drag to select card regions")
        print("2. Press 'r' to refresh screenshot")
        print("3. Press 'q' to quit")
        
        # Create window with scrollbars
        cv2.namedWindow('Capture Cards', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Capture Cards', 800, 1200)  # Set initial window size
        cv2.setMouseCallback('Capture Cards', self.mouse_callback)
        
        # Initial screenshot
        screen = self.take_screenshot()
        cv2.imshow('Capture Cards', screen)
        
        while True:
            key = cv2.waitKey(50) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                print("Refreshing screenshot...")
                screen = self.take_screenshot()
                cv2.imshow('Capture Cards', screen)
        
        cv2.destroyAllWindows()

def main():
    try:
        capturer = CardTemplateCapture()
        capturer.capture_templates()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()