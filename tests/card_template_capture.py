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
        self.template_count = 0

    def take_screenshot(self):
        """Take a screenshot of the device and convert it to an OpenCV image."""
        screenshot_data = self.device.screencap()
        nparr = np.frombuffer(screenshot_data, np.uint8)
        self.current_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return self.current_image.copy()
    
    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events for selecting regions."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
        
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            # Create a copy of the original image to draw the rectangle
            temp_img = self.current_image.copy()
            cv2.rectangle(temp_img, self.start_point, (x, y), (0, 255, 0), 2)
            cv2.imshow('Capture Cards', temp_img)
        
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.end_point = (x, y)
            
            # Calculate rectangle coordinates
            x1 = min(self.start_point[0], self.end_point[0])
            y1 = min(self.start_point[1], self.end_point[1])
            x2 = max(self.start_point[0], self.end_point[0])
            y2 = max(self.start_point[1], self.end_point[1])
            
            # Extract and save the selected region
            if (x2 - x1) > 0 and (y2 - y1) > 0:
                card = self.current_image[y1:y2, x1:x2]
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
        
        cv2.namedWindow('Capture Cards')
        cv2.setMouseCallback('Capture Cards', self.mouse_callback)
        
        # Initial screenshot before entering the loop
        screen = self.take_screenshot()
        cv2.imshow('Capture Cards', screen)

        while True:
            # Show the current image (don't re-screenshot unless needed)
            cv2.imshow('Capture Cards', screen)
            
            key = cv2.waitKey(50) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                # Refresh screenshot
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
