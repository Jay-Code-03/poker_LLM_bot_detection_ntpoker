import cv2
import numpy as np
from ppadb.client import Client as AdbClient

def main():
    # 1. Connect to ADB
    adb = AdbClient(host="127.0.0.1", port=5037)
    devices = adb.devices()

    if not devices:
        raise Exception("No devices found. Make sure your emulator is running.")

    device = devices[0]
    print(f"Connected to {device.serial}")

    # 2. Take a screenshot
    screenshot_data = device.screencap()
    if not screenshot_data:
        raise Exception("Failed to take a screenshot.")

    # 3. Convert screenshot bytes to a NumPy array
    nparr = np.frombuffer(screenshot_data, np.uint8)
    screen_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 4. Load your reference image of the Gmail icon
    gmail_icon = cv2.imread('card_templates/hero_card_3c.png', cv2.IMREAD_COLOR)
    if gmail_icon is None:
        raise FileNotFoundError("Could not find 'gmail_icon.png' in the current directory.")

    # 5. Run template matching
    result = cv2.matchTemplate(screen_img, gmail_icon,cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    # 6. Define a threshold for a "good" match
    threshold = 0.8  # Adjust as needed. 0.8 or 0.9 are common values.

    if max_val >= threshold:
        # Template found with high confidence
        print(f"Gmail icon found with confidence: {max_val:.2f}")

        # Find the center of the matched region
        icon_height, icon_width, _ = gmail_icon.shape
        center_x = max_loc[0] + icon_width // 2
        center_y = max_loc[1] + icon_height // 2

        print(f"Clicking on Gmail icon at: ({center_x}, {center_y})")
        device.shell(f"input tap {center_x} {center_y}")
    else:
        print(f"Gmail icon not found. Best match confidence: {max_val:.2f}")

if __name__ == "__main__":
    main()