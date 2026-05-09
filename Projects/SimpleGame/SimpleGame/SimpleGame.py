import cv2
import numpy as np
import time
from cvzone.HandTrackingModule import HandDetector
from collections import deque

class Button:
    def __init__(self, pos, text, size=(250, 80), color=(0, 200, 255), text_color=(255, 255, 255)):
        self.pos = pos
        self.size = size
        self.text = text
        self.color = color
        self.text_color = text_color
        self.radius = 15  # Rounded corners radius
        self.hover = False
        self.clicked = False
        self.padding = 20  # Padding around text for click area
        
    def draw(self, img):
        x, y = self.pos
        w, h = self.size
        
        # Draw button background
        cv2.rectangle(img, (x, y), (x + w, y + h), self.color, -1)
        
        # Only show hover/click effects when the button is being interacted with
        if self.hover or self.clicked:
            # Add highlight effect when hovered or clicked
            highlight = img.copy()
            highlight_color = (255, 255, 255) if self.clicked else (230, 230, 230)
            # Draw border that matches the clickable area
            cv2.rectangle(highlight, (x, y), (x + w, y + h), highlight_color, 2)
            cv2.addWeighted(highlight, 0.3, img, 0.7, 0, img)
            
            # Add a subtle glow effect on click
            if self.clicked:
                glow = img.copy()
                cv2.rectangle(glow, (x-2, y-2), (x + w + 2, y + h + 2), (255, 255, 200), 2)
                cv2.addWeighted(glow, 0.2, img, 0.8, 0, img)
        
        # Add subtle hover effect
        if self.hover:
            overlay = img.copy()
            # Only slightly lighten the button on hover
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (255, 255, 255), -1, cv2.LINE_AA)
            alpha = 0.1  # Very subtle hover effect
            cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
        
        # Add text
        text_size = cv2.getTextSize(self.text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]
        text_x = x + (w - text_size[0]) // 2
        text_y = y + (h + text_size[1]) // 2 + 5
        
        # Text shadow
        cv2.putText(img, self.text, (text_x + 2, text_y + 2), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0, 150), 2, cv2.LINE_AA)
        # Main text
        cv2.putText(img, self.text, (text_x, text_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, self.text_color, 2, cv2.LINE_AA)
        
        return img
    
    def check_click(self, x, y, fingers_up, hand_center):
        if hand_center is None:
            self.hover = False
            self.clicked = False
            return False
            
        # Get text dimensions
        (text_w, text_h), _ = cv2.getTextSize(self.text, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)
        
        # Calculate text boundaries with small padding
        padding = 10
        text_left = self.pos[0] - text_w // 2 - padding
        text_right = self.pos[0] + text_w // 2 + padding
        text_top = self.pos[1] - text_h // 2 - padding
        text_bottom = self.pos[1] + text_h // 2 + padding
        
        # Check if hand is within the text bounds
        in_bounds = (text_left < hand_center[0] < text_right and 
                    text_top < hand_center[1] < text_bottom)
        
        # For debugging: Draw the clickable area
        if hasattr(self, 'debug') and self.debug:
            cv2.rectangle(img, 
                        (int(text_left), int(text_top)), 
                        (int(text_right), int(text_bottom)), 
                        (0, 255, 0), 1)
        
        # Update hover state
        self.hover = in_bounds
        
        # Only trigger click if we're hovering and this is a new click
        if self.hover and not self.clicked:
            self.clicked = True
            print(f"Button {self.text} clicked!")
            return True
            
        # Reset click state if not hovering
        if not self.hover:
            self.clicked = False
            
        return False

class GameUI:
    def __init__(self):
        # Initialize camera
        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        
        # Initialize hand detector with optimized parameters
        self.detector = HandDetector(
            staticMode=False,
            maxHands=1,
            modelComplexity=1,
            detectionCon=0.7,  # Slightly lower for better detection
            minTrackCon=0.6     # Minimum tracking confidence
        )
        
        # No smoothing - direct hand position tracking
        self.prev_hand_pos = None
        
        # UI Elements
        self.menu_buttons = [
            Button((640, 460), "START GAME", color=(0, 200, 255))  # Centered horizontally
        ]
        
        # Test mode selection buttons
        self.test_mode_buttons = [
            Button((640, 360), "Place the box on the Hole", color=(100, 200, 100))
        ]
        
        # Back button (positioned at top left)
        self.back_button = Button((80, 60), "← Back", size=(120, 50), color=(100, 100, 100))
        
        # Game state
        self.running = True
        self.current_screen = "menu"  # menu, test_mode, game, instructions
        
        # Colors
        self.COLORS = {
            "bg": (240, 240, 250),
            "title": (50, 50, 100),
            "subtitle": (100, 100, 150)
        }
    
    def draw_gradient_background(self, img):
        """Draw a gradient background"""
        h, w = img.shape[:2]
        for y in range(h):
            # Create a gradient from light blue to light purple
            r = int(240 + (y/h) * 15)
            g = int(240 + (y/h) * 15)
            b = int(250 - (y/h) * 30)
            cv2.line(img, (0, y), (w, y), (b, g, r), 1)
        return img
    
    def draw_menu(self, img, hand_pos=None):
        """Draw the main menu"""
        h, w = img.shape[:2]
        
        # Draw gradient background
        img = self.draw_gradient_background(img)
        
        # Add decorative elements
        cv2.ellipse(img, (w//4, h//3), (150, 150), 0, 0, 360, (200, 230, 255), -1)
        cv2.ellipse(img, (3*w//4, 2*h//3), (200, 200), 0, 0, 360, (230, 220, 255), -1)
        
        # Add title with shadow
        title = "Children's Cognitive Ability Test"
        subtitle = "Touch with your finger to interact"
        
        # Title shadow
        cv2.putText(img, title, (w//2 - 400 + 3, 200 + 3), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0, 150), 3, cv2.LINE_AA)
        # Main title
        cv2.putText(img, title, (w//2 - 400, 200), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, self.COLORS["title"], 3, cv2.LINE_AA)
        
        # Subtitle
        cv2.putText(img, subtitle, (w//2 - 200, 270), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.COLORS["subtitle"], 2, cv2.LINE_AA)
        
        # Draw menu buttons
        for button in self.menu_buttons:
            button.draw(img)
        
        # Draw hand position indicator if hand is detected
        if hand_pos:
            cv2.circle(img, hand_pos, 15, (0, 0, 255), -1)
            cv2.circle(img, hand_pos, 10, (0, 255, 0), -1)
        
        return img
        
    def draw_test_mode_screen(self, img, hand_pos=None):
        """Draw the test mode selection screen"""
        h, w = img.shape[:2]
        
        # Draw gradient background
        img = self.draw_gradient_background(img)
        
        # Draw back button
        self.back_button.draw(img)
        
        # Draw title
        title = "Select Test Mode"
        cv2.putText(img, title, (w//2 - 150 + 3, 100 + 3), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0, 150), 3, cv2.LINE_AA)
        cv2.putText(img, title, (w//2 - 150, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (50, 50, 150), 3, cv2.LINE_AA)
        
        # Draw test mode buttons
        for button in self.test_mode_buttons:
            button.draw(img)
        
        # Draw hand position indicator if hand is detected
        if hand_pos:
            cv2.circle(img, hand_pos, 15, (0, 0, 255), -1)
            cv2.circle(img, hand_pos, 10, (0, 255, 0), -1)
        
        return img
    
    def smooth_hand_position(self, new_pos):
        """Direct hand position - no smoothing"""
        return new_pos
    
    def run(self):
        """Main game loop"""
        prev_time = time.time()
        
        while self.running:
            # Calculate FPS with safety check
            current_time = time.time()
            time_diff = current_time - prev_time
            fps = 1.0 / time_diff if time_diff > 0 else 60.0  # Default to 60 FPS if time_diff is 0
            prev_time = current_time
            
            success, img = self.cap.read()
            if not success:
                continue
                
            img = cv2.flip(img, 1)  # Mirror the frame
            img_clean = img.copy()
            
            # Find hands with optimized parameters
            hands = self.detector.findHands(
                img,
                flipType=False,
                draw=False  # We'll draw our own landmarks
            )
            
            # Create a clean copy for our custom drawing
            img_landmarks = img.copy()
            
            hand_pos = None
            fingers_up = []
            
            if hands and len(hands) > 0:
                hand = hands[0]
                if 'lmList' not in hand or len(hand['lmList']) < 21:  # 21 landmarks in MediaPipe hand model
                    hand_pos = None
                    fingers_up = []
                else:
                    landmarks = hand['lmList']
                    
                    # Draw all hand landmarks
                    for lm in landmarks:
                        x, y = int(lm[0]), int(lm[1])
                        cv2.circle(img_landmarks, (x, y), 5, (0, 255, 0), -1)
                    
                    # Draw connections between landmarks
                    connections = [
                        (0,1),(1,2),(2,3),(3,4),         # Thumb
                        (0,5),(5,6),(6,7),(7,8),         # Index
                        (5,9),(9,10),(10,11),(11,12),    # Middle
                        (9,13),(13,14),(14,15),(15,16),  # Ring
                        (13,17),(17,18),(18,19),(19,20), # Pinky
                        (0,17)  # Connect wrist to pinky base
                    ]
                    
                    for start, end in connections:
                        if start < len(landmarks) and end < len(landmarks):
                            start_pos = (int(landmarks[start][0]), int(landmarks[start][1]))
                            end_pos = (int(landmarks[end][0]), int(landmarks[end][1]))
                            cv2.line(img_landmarks, start_pos, end_pos, (0, 255, 0), 2)
                    
                    # Use index finger tip for interaction
                    index_tip = hand['lmList'][8]
                    hand_pos = (int(index_tip[0]), int(index_tip[1]))
                    
                    # Draw a circle at the index finger tip (slightly larger for visibility)
                    cv2.circle(img_landmarks, hand_pos, 10, (0, 0, 255), -1)
                    
                    # Combine the landmarks with the original image
                    img = cv2.addWeighted(img, 0.7, img_landmarks, 0.3, 0)
                    
                    # Get which fingers are up
                    fingers_up = self.detector.fingersUp(hand)
                    
                    # Store for potential smoothing
                    self.prev_hand_pos = hand_pos
            else:
                hand_pos = self.prev_hand_pos
                fingers_up = []
            
            # Debug: Show hand position
            if hand_pos:
                cv2.putText(img, f"Hand: {hand_pos}", (20, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Handle button interactions based on current screen
            if hand_pos:
                if self.current_screen == "menu":
                    for button in self.menu_buttons:
                        if button.check_click(hand_pos[0], hand_pos[1], fingers_up, hand_pos):
                            if button.text == "START GAME":
                                self.current_screen = "test_mode"
                                print("Test mode selection screen")
                                break  # Only process one click per frame
                                
                elif self.current_screen == "test_mode":
                    # Check back button
                    if self.back_button.check_click(hand_pos[0], hand_pos[1], fingers_up, hand_pos):
                        self.current_screen = "menu"
                        print("Returning to main menu")
                    else:
                        # Check test mode buttons
                        for button in self.test_mode_buttons:
                            if button.check_click(hand_pos[0], hand_pos[1], fingers_up, hand_pos):
                                print(f"Selected test: {button.text}")
                                # Add test start logic here
                                break  # Only process one click per frame
            
            # Draw the appropriate screen
            if self.current_screen == "menu":
                img = self.draw_menu(img, hand_pos)
            elif self.current_screen == "test_mode":
                img = self.draw_test_mode_screen(img, hand_pos)
            
            # Show the frame with 70% opacity over the camera feed
            overlay = img.copy()
            alpha = 0.7
            cv2.addWeighted(overlay, alpha, img_clean, 1 - alpha, 0, img)
            
            # Display the frame
            cv2.imshow("Children's Cognitive Ability Test", img)
            
            # Check for key press
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC key
                self.running = False
                
        # Clean up
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    game = GameUI()
    game.run()