import cv2
import numpy as np
import os
from ppadb.client import Client as AdbClient

class EmulatorScreenshotCollector:
    def __init__(self):
        # Directory to save full screenshots
        self.output_dir = 'emulator_screens'
        os.makedirs(self.output_dir, exist_ok=True)

        # Initialize ADB
        self.adb = AdbClient(host="127.0.0.1", port=5037)
        devices = self.adb.devices()
        
        if not devices:
            raise Exception("No devices found. Make sure your emulator is running.")
        
        self.device = devices[0]
        print(f"Connected to: {self.device.serial}")

        # Keep track of screenshot count
        self.screenshot_count = 0 #ccc

    def capture_screenshot(self):
        """Captures a full-resolution screenshot from the emulator."""
        screenshot_data = self.device.screencap()
        nparr = np.frombuffer(screenshot_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img

    def save_screenshot(self, img):
        """Saves the screenshot to disk in the output folder."""
        filename = os.path.join(self.output_dir, f'screen_{self.screenshot_count}.png')
        cv2.imwrite(filename, img)
        print(f"Saved screenshot: {filename}")
        self.screenshot_count += 1

    def run(self):
        """
        Main loop:
        - Press 'c' to capture a new screenshot
        - Press 'q' to quit
        """
        print("Controls:\n" 
              "  c = Capture screenshot\n"
              "  q = Quit\n")

        while True:
            key = input("Press 'c' to capture, 'q' to quit: ").lower()
            
            if key == 'q':
                print("Exiting...")
                break
            elif key == 'c':
                # Capture
                img = self.capture_screenshot()
                # Save
                self.save_screenshot(img)
            else:
                print("Invalid input. Please enter 'c' or 'q'.")

def main():
    collector = EmulatorScreenshotCollector()
    collector.run()

if __name__ == "__main__":
    main()
