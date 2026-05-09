"""
License Plate Recognition System

This module provides functionality to detect and recognize license plates
using computer vision and OCR techniques.
"""

import re
from datetime import datetime
from typing import Tuple, List, Pattern, Dict, Any

import cv2
import numpy as np
import pytesseract
import easyocr

# Initialize EasyOCR reader
reader = easyocr.Reader(['en'])

# Set path to tesseract executable
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\Jb Home\OneDrive\Documents\Tesseract\tesseract.exe"

# Compile regex patterns once for better performance
PLATE_PATTERNS = [
    (re.compile(r'^([A-Z]{3})([0-9]{4})$'), r'\1-\2'),      # ABC1234 -> ABC-1234
    (re.compile(r'^([A-Z]{3})[^0-9]*([0-9]{4})$'), r'\1-\2'), # ABC 1234 -> ABC-1234
    (re.compile(r'^([0-9]{3})([A-Z]{3})$'), r'\1-\2'),      # 123ABC -> 123-ABC
    (re.compile(r'^([0-9]{3})[^A-Z]*([A-Z]{3})$'), r'\1-\2')  # 123 ABC -> 123-ABC
]

# Compile regex patterns for plate validation
INVALID_PLATE_PATTERNS = [
    re.compile(r'^[A-Z]{3}-\d{1,2}$'),    # ABC-1, ABC-12
    re.compile(r'^[A-Z]{4}-?\d{2,3}$'),   # ABCD-12, ABCD-123
    re.compile(r'^[A-Z]{4}-\d{4}$'),      # ABCD-1234
    re.compile(r'^[A-Z]{2,4}\d{1,2}$'),   # AB1, ABC1, ABCD1, AB12, etc.
    re.compile(r'^[A-Z]{5,}')              # ABCDE... (too many letters)
]

VALID_PLATE_PATTERNS = [
    re.compile(r'^[A-Z]{3}-?\d{3,4}$'),   # ABC-123, ABC-1234, ABC123, ABC1234
]

def format_plate_text(text: str) -> str:
    """
    Format text to match standard Philippine license plate format (ABC-1234).
    
    Args:
        text: Input text to format
        
    Returns:
        Formatted plate text
    """
    if not text:
        return ""
        
    clean_text = ''.join(c.upper() for c in text if c.isalnum())
    
    for pattern, replacement in PLATE_PATTERNS:
        if pattern.match(clean_text):
            return pattern.sub(replacement, clean_text)
    
    # Fallback: first 3 letters followed by numbers
    if len(clean_text) > 3:
        return f"{clean_text[:3]}-{clean_text[3:7]}"
    return clean_text

def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """
    Preprocess image to improve OCR text recognition.
    
    Args:
        image: Input BGR image
        
    Returns:
        Preprocessed grayscale image optimized for OCR
    """
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        blurred, 255, 
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY_INV, 
        11, 4
    )
    
    # Apply dilation to make text more solid
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    return cv2.dilate(thresh, kernel, iterations=1)


# Compile regex patterns once for better performance
INVALID_PLATE_PATTERNS = [
    re.compile(r'^[A-Z]{3}-\d{1,2}$'),    # ABC-1, ABC-12
    re.compile(r'^[A-Z]{4}-?\d{2,3}$'),   # ABCD-12, ABCD-123
    re.compile(r'^[A-Z]{4}-\d{4}$'),      # ABCD-1234
    re.compile(r'^[A-Z]{2,4}\d{1,2}$'),   # AB1, ABC1, ABCD1, AB12, etc.
    re.compile(r'^[A-Z]{5,}')              # ABCDE... (too many letters)
]

VALID_PLATE_PATTERNS = [
    re.compile(r'^[A-Z]{3}-?\d{3,4}$'),   # ABC-123, ABC-1234, ABC123, ABC1234
]

def is_valid_plate_text(text: str) -> Tuple[str, bool]:
    """
    Validate if the detected text matches Philippine license plate format.
    
    Args:
        text: Text to validate
        
    Returns:
        Tuple of (cleaned_text, is_valid) where:
        - cleaned_text: Formatted text if valid, original text otherwise
        - is_valid: Boolean indicating if the text matches a valid plate format
    """
    if not text:
        return "", False
    
    # Clean and standardize the input text
    clean_text = ''.join(c.upper() for c in text if c.isalnum() or c == '-')
    
    # Check against invalid patterns first (faster to fail)
    if any(pattern.match(clean_text) for pattern in INVALID_PLATE_PATTERNS):
        return clean_text, False
    
    # Check against valid patterns
    for pattern in VALID_PLATE_PATTERNS:
        if pattern.match(clean_text):
            # Format the text to standard format (ABC-123 or ABC-1234)
            if '-' in clean_text:
                return clean_text, True
            else:
                # If no dash, add it after the first 3 characters
                return f"{clean_text[:3]}-{clean_text[3:]}", True
    
    return clean_text, False

def detect_with_ocr(image: np.ndarray) -> str:
    """
    Detect text in an image using Tesseract OCR with preprocessing.
    
    Args:
        image: Input BGR image
        
    Returns:
        Detected and cleaned text string
    """
    processed = preprocess_for_ocr(image)
    custom_config = (
        r'--oem 3 --psm 7 '
        r'-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789- '
    )
    
    try:
        data = pytesseract.image_to_data(
            processed, 
            config=custom_config, 
            output_type=pytesseract.Output.DICT
        )
        
        conf_threshold = 30
        potential_texts = []
        
        for i, text in enumerate(data['text']):
            if (int(data['conf'][i]) > conf_threshold and 
                len(text.strip()) >= 3 and
                any(c.isalnum() for c in text)):
                potential_texts.append(text.strip())
        
        combined_text = ' '.join(potential_texts)
        return ''.join(c.upper() for c in combined_text if c.isalnum() or c in ' -')
    except Exception as e:
        print(f"OCR detection error: {str(e)}")
        return ""

def detect_handwriting(image: np.ndarray) -> str:
    """
    Detect handwritten text in an image using EasyOCR.
    
    Args:
        image: Input BGR image
        
    Returns:
        Detected and cleaned text string
    """
    if image is None or image.size == 0:
        return ""
        
    try:
        # Convert BGR to RGB (EasyOCR expects RGB)
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Get predictions with confidence threshold
        results = reader.readtext(
            rgb_image, 
            detail=0, 
            paragraph=True,
            min_size=10,  # Minimum text size to consider
            contrast_ths=0.1,  # Lower is more sensitive to low contrast text
            adjust_contrast=0.5  # Adjust contrast for better detection
        )
        
        if results:
            # Join all detected text and clean it up
            combined = ' '.join(str(text).strip() for text in results if text.strip())
            return ''.join(c.upper() for c in combined if c.isalnum() or c in ' -')
        return ""
    except Exception as e:
        print(f"Handwriting recognition error: {str(e)}")
        return ""

def detect_text(image: np.ndarray) -> str:
    """
    Detect and recognize text in an image using both OCR and handwriting recognition.
    
    This function first attempts to detect text using standard OCR (Tesseract).
    If that fails to find valid plate text, it falls back to handwriting recognition (EasyOCR).
    
    Args:
        image: Input BGR image containing potential license plate text
        
    Returns:
        Formatted license plate text if valid text is found, empty string otherwise
    """
    if image is None or image.size == 0:
        return ""
    
    # First try standard OCR
    ocr_text = detect_with_ocr(image)
    if ocr_text and is_valid_plate_text(ocr_text)[1]:
        return format_plate_text(ocr_text)
    
    # If OCR fails, try handwriting recognition
    hw_text = detect_handwriting(image)
    if hw_text and is_valid_plate_text(hw_text)[1]:
        return format_plate_text(hw_text)
    
    return ""

def main():
    """Main function to run the license plate recognition system."""
    # Set path to tesseract executable
    pytesseract.pytesseract.tesseract_cmd = r"C:\Users\Jb Home\OneDrive\Documents\Tesseract\tesseract.exe"

    # Initialize webcam
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    print("License Plate Reader - Press 'q' to quit")
    print("Click the 'Detect' button to scan for license plates")

    # Initialize state
    detection_requested = False
    last_detection = ""
    last_detection_time = 0
    is_valid_plate = False

    # Create a window with a reasonable size
    cv2.namedWindow('License Plate Reader', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('License Plate Reader', 1000, 700)

    def mouse_callback(event, x, y, flags, param):
        nonlocal detection_requested
        
        # Check if the click is within the button area
        button_x1, button_y1 = 20, 20
        button_x2, button_y2 = 200, 80
        
        if event == cv2.EVENT_LBUTTONDOWN:
            if (button_x1 <= x <= button_x2 and button_y1 <= y <= button_y2):
                detection_requested = True
                print("Detection requested...")

    # Set mouse callback
    cv2.setMouseCallback('License Plate Reader', mouse_callback)

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame")
                break
            
            # Create a copy of the frame for display
            display_frame = frame.copy()
            
            # Get current time
            current_time = datetime.now().timestamp()
            
            # Create a rectangular region of interest (center of the frame)
            height, width = frame.shape[:2]
            
            # Define rectangle dimensions (wider than tall, like a license plate)
            roi_width = min(width, height) * 2 // 3
            roi_height = roi_width // 3  # Standard license plate aspect ratio is about 3:1
            
            # Calculate position to center the rectangle
            x1 = (width - roi_width) // 2
            y1 = (height - roi_height) // 2
            x2 = x1 + roi_width
            y2 = y1 + roi_height
            
            # Draw ROI rectangle
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(display_frame, "Position plate here", 
                       (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.7, (0, 255, 0), 2)
            
            # Draw the detection button
            button_color = (0, 200, 0) if not detection_requested else (0, 0, 200)
            cv2.rectangle(display_frame, (20, 20), (200, 80), button_color, -1)
            cv2.putText(display_frame, 'DETECT', (50, 55), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Process detection if button was clicked
            if detection_requested:
                # Process only the ROI
                roi = frame[y1:y2, x1:x2]
                
                # Detect text in the ROI
                detected_text = detect_text(roi)
                
                if detected_text:
                    # Validate the plate format
                    formatted_text, is_valid = is_valid_plate_text(detected_text)
                    
                    # Store both the plate text and its validity
                    last_detection = formatted_text if is_valid else detected_text
                    is_valid_plate = is_valid
                    last_detection_time = current_time
                    
                    status = "VALID" if is_valid else "INVALID"
                    print(f"Detected: {last_detection} - {status}")
                
                # Reset the flag
                detection_requested = False
            
            # Display the last detection status and plate number
            if last_detection and (current_time - last_detection_time < 5):  # Show for 5 seconds
                # Draw a semi-transparent background for the status box
                overlay = display_frame.copy()
                cv2.rectangle(overlay, (width - 300, 20), (width - 20, 100), (40, 40, 40), -1)
                cv2.addWeighted(overlay, 0.7, display_frame, 0.3, 0, display_frame)
                
                # Draw plate number (always show the detected text)
                plate_text = f"Plate: {last_detection}"
                cv2.putText(display_frame, plate_text, 
                           (width - 280, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 
                           0.7, (255, 255, 255), 2)
                
                # Draw validation status
                status_text = "VALID" if is_valid_plate else "INVALID"
                status_color = (0, 255, 0) if is_valid_plate else (0, 0, 255)
                
                # Draw the status text
                cv2.putText(display_frame, f"Status: {status_text}", 
                           (width - 280, 80), 
                           cv2.FONT_HERSHEY_SIMPLEX, 
                           0.7, status_color, 2)
            
            # Add help text
            cv2.putText(display_frame, "1. Position the license plate in the green box", 
                       (20, height - 60), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.6, (0, 255, 0), 1)
            cv2.putText(display_frame, "2. Click the red DETECT button to scan", 
                       (20, height - 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       0.6, (0, 255, 0), 1)
            
            # Show the frame
            cv2.imshow('License Plate Reader', display_frame)
            
            # Exit on 'q' key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        # Release resources
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

def preprocess_image(img):
    """Preprocess the image for better plate detection"""
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply bilateral filter to reduce noise while keeping edges sharp
    gray = cv2.bilateralFilter(gray, 11, 17, 17)
    
    # Apply adaptive thresholding
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                 cv2.THRESH_BINARY, 11, 2)
    
    return thresh

def detect_plate(img):
    """Detect license plate in the image"""
    # Preprocess the image
    processed = preprocess_image(img)
    
    # Find contours
    contours, _ = cv2.findContours(processed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    # Sort contours by area in descending order
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
    
    plate_contour = None
    
    # Loop through contours to find the best plate candidate
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.018 * perimeter, True)
        
        # If we found a quadrilateral
        if len(approx) == 4:
            plate_contour = approx
            break
    
    return plate_contour

def extract_plate(img, contour):
    """Extract and warp the plate region"""
    # Get the four corners of the contour
    pts = contour.reshape(4, 2)
    rect = np.zeros((4, 2), dtype="float32")
    
    # The top-left point has the smallest sum
    # The bottom-right point has the largest sum
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    
    # The top-right point has the smallest difference
    # The bottom-left point has the largest difference
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    
    # Get the dimensions of the new image
    (tl, tr, br, bl) = rect
    widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
    widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
    maxWidth = max(int(widthA), int(widthB))
    
    heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
    heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
    maxHeight = max(int(heightA), int(heightB))
    
    # Define the destination points for the perspective transform
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]], dtype="float32")
    
    # Compute the perspective transform matrix and apply it
    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
    
    return warped

def read_plate_number(plate_img):
    """Extract text from the plate image using OCR"""
    # Convert to grayscale
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    
    # Apply thresholding to get binary image
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Use Tesseract to do OCR on the processed image
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    text = pytesseract.image_to_string(thresh, config=custom_config)
    
    # Clean up the text
    text = ''.join(e for e in text if e.isalnum())
    
    return text

def print_plate_number(plate_number):
    """Print the detected plate number with timestamp"""
    if len(plate_number) > 4:  # Basic validation
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"{timestamp} - Detected plate: {plate_number}")

print("License Plate Detection System")
print("Press 's' to save current frame")
print("Press 'q' to quit")

# Main loop
plate_detected = False
last_plate = ""
last_detection_time = 0
MIN_TIME_BETWEEN_DETECTIONS = 5  # seconds

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Create a copy of the frame for display
    display_frame = frame.copy()
    
    # Try to detect a license plate
    plate_contour = detect_plate(frame)
    
    if plate_contour is not None:
        # Draw the contour of the detected plate
        cv2.drawContours(display_frame, [plate_contour], -1, (0, 255, 0), 2)
        
        # Extract and process the plate
        plate_img = extract_plate(frame, plate_contour)
        
        # Only process if plate is large enough
        if plate_img.shape[0] > 30 and plate_img.shape[1] > 80:
            # Read the plate number
            plate_number = read_plate_number(plate_img)
            
            current_time = datetime.now().timestamp()
            
            # Only process if enough time has passed since last detection
            if (current_time - last_detection_time > MIN_TIME_BETWEEN_DETECTIONS or 
                plate_number != last_plate) and len(plate_number) >= 4:
                
                last_plate = plate_number
                last_detection_time = current_time
                print_plate_number(plate_number)
                
                # Show the detected plate in a separate window
                cv2.imshow('Detected Plate', plate_img)
                
            # Display the plate number on the frame
            cv2.putText(display_frame, f'Plate: {last_plate}', 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                       1, (0, 255, 0), 2)
    
    # Display instructions
    cv2.putText(display_frame, "Press 's' to save current frame", 
               (10, frame.shape[0] - 20), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
    
    # Show the frame
    cv2.imshow('License Plate Detection', display_frame)
    
    # Key controls
    key = cv2.waitKey(1) & 0xff
    if key == ord('q'):
        break
    elif key == ord('s'):  # Save current frame
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cv2.imwrite(f'capture_{timestamp}.jpg', frame)
        print(f"Frame saved as capture_{timestamp}.jpg")

# Release resources
cap.release()
cv2.destroyAllWindows()
