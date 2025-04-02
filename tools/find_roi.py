import cv2
import numpy as np
from ppadb.client import Client as AdbClient
import pytesseract

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

def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        screen = param['screen']
        # Name each offset set
        offset_configs = [
            {
                "name": "offset1",
                "values": (10, -20, 110, 30)    # Starts at button center, wider
            },
            {
                "name": "offset2", 
                "values": (15, -30, 120, 40)  # Starts left of button, even wider
            },
            {
                "name": "offset3",
                "values": (30, -20, 150, 50)   # Slight right start, medium width
            }
        ]
        
        for config in offset_configs:
            name = config["name"]
            offset = config["values"]
            
            x1 = x + offset[0]
            y1 = y + offset[1]
            x2 = x + offset[2]
            y2 = y + offset[3]
            
            # Extract ROI
            roi = screen[y1:y2, x1:x2]
            if roi.size == 0:
                continue
                
            # Draw rectangle on copy of screen to show ROI
            screen_copy = screen.copy()
            cv2.rectangle(screen_copy, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.imwrite(f"roi_box_{name}.png", screen_copy)
            
            # Save ROI for inspection
            cv2.imwrite(f"roi_{name}.png", roi)
            
            # Try to detect text
            text = pytesseract.image_to_string(roi, config='--psm 7 digits')
            print(f"\nOffset set: {name}")
            print(f"Clicked at ({x}, {y})")
            print(f"ROI coordinates: ({x1}, {y1}) to ({x2}, {y2})")
            print(f"Detected text: {text}")

def main():
    device = connect_device()
    screen = capture_screen(device)
    
    # Create window and set callback
    window_name = 'Click on R/B button to test ROI'
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, mouse_callback, {'screen': screen})
    
    print("Click on R/B buttons to test different ROI sizes")
    print("Press 'q' to quit")
    
    while True:
        cv2.imshow(window_name, screen)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()