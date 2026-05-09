# import cv2
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import os
import numpy as np
import face_recognition
import time
import subprocess

# Path to save the owner's face image
OWNER_FACE_PATH = 'owner_face.jpg'
# Path to Haar cascade file (ensure this is present in the project directory)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CASCADE_PATH = os.path.join(BASE_DIR, 'haarcascade_frontalface_default.xml')

class FaceRegisterApp:
    def start_monitoring(self):
        self.window.destroy()
        root = tk.Tk()
        MonitorApp(root, "Owner Presence Monitor")
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.video_source = 0
        self.vid = cv2.VideoCapture(self.video_source)
        self.canvas_width = 400
        self.canvas_height = 300
        self.canvas = tk.Canvas(window, width=self.canvas_width, height=self.canvas_height)
        self.canvas.pack()

        self.btn_snapshot = tk.Button(window, text="Register Face", width=50, command=self.snapshot, state=tk.DISABLED)
        self.btn_snapshot.pack(anchor=tk.CENTER, expand=True)

        # Load Haar cascade for face detection
        self.face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
        if self.face_cascade.empty():
            messagebox.showerror("Error", f"Could not load Haar cascade from {CASCADE_PATH}")
            self.window.destroy()
            return

        # Box parameters (centered)
        self.box_w = 180
        self.box_h = 180
        self.box_x1 = (self.canvas_width - self.box_w) // 2
        self.box_y1 = (self.canvas_height - self.box_h) // 2
        self.box_x2 = self.box_x1 + self.box_w
        self.box_y2 = self.box_y1 + self.box_h

        self.face_in_box = False
        self.last_frame = None
        self.delay = 15
        self.update()
        self.window.mainloop()

    def snapshot(self):
        if self.last_frame is not None and self.face_in_box:
            try:
                print(f"[DEBUG] Attempting snapshot with frame shape: {self.last_frame.shape}")
                # Create a smaller frame for face detection (faster processing)
                small_frame = cv2.resize(self.last_frame, (0, 0), fx=0.5, fy=0.5)
                gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
                print(f"[DEBUG] Converted to grayscale: {gray.shape}")
                
                # Detect faces with adjusted parameters
                faces = self.face_cascade.detectMultiScale(
                    gray, 
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(40, 40)  # Adjusted for smaller frame
                )
                print(f"[DEBUG] Face detection result: {len(faces)} faces found")

                if len(faces) == 0:
                    messagebox.showerror("Error", "No face detected. Please try again.")
                    return
                
                # Find the largest face
                largest_face = None
                max_area = 0
                for (x, y, w, h) in faces:
                    area = w * h
                    if area > max_area:
                        max_area = area
                        largest_face = (x, y, w, h)
                
                if largest_face is None:
                    messagebox.showerror("Error", "No face detected. Please try again.")
                    return
                    
                # Scale up coordinates for the original frame
                x, y, w, h = largest_face
                x *= 2
                y *= 2
                w *= 2
                h *= 2
                
                # Get the face ROI and convert to RGB
                face_img = self.last_frame[y:y+h, x:x+w]
                rgb_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                
                # Get face landmarks for better encoding
                face_landmarks = face_recognition.face_landmarks(rgb_face)
                
                if not face_landmarks:
                    messagebox.showerror("Error", "Could not detect facial features. Please try again.")
                    return
                
                # Encode the face using landmarks
                face_encodings = face_recognition.face_encodings(rgb_face, face_landmarks)
                
                if not face_encodings:
                    messagebox.showerror("Error", "Could not encode face. Please try again.")
                    return
                
                # If we got here, we have a good face encoding
                # If owner_face.jpg exists, require PIN to overwrite
                if os.path.exists(OWNER_FACE_PATH):
                    self.prompt_pin_and_save(face_img, face_encodings[0])
                else:
                    self.prompt_new_pin_and_save(face_img, face_encodings[0])
                    
            except Exception as e:
                print(f"[DEBUG] Snapshot error: {e}")
                messagebox.showerror("Error", f"An error occurred: {str(e)}")
        else:
            messagebox.showerror("Error", "No face detected. Please position your face in the frame.")

    def prompt_new_pin_and_save(self, face_img, face_encoding):
        def save_pin():
            pin = pin_entry.get()
            if len(pin) == 4 and pin.isdigit():
                try:
                    # Save the face image
                    cv2.imwrite(OWNER_FACE_PATH, face_img)
                    
                    # Save the face encoding
                    np.save('owner_face_encoding.npy', face_encoding)
                    
                    # Save the PIN
                    with open("owner_pin.txt", "w") as f:
                        f.write(pin)
                        
                    pin_win.destroy()
                    messagebox.showinfo("Success", "Owner's face and PIN have been saved.")
                    self.window.after(100, self.start_monitoring)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save: {str(e)}")
            else:
                messagebox.showerror("Error", "PIN must be a 4-digit number.")

        pin_win = tk.Toplevel(self.window)
        pin_win.title("Set Owner PIN")
        tk.Label(pin_win, text="Enter new 4-digit PIN:").pack(pady=5)
        pin_entry = tk.Entry(pin_win, show='*', width=10, font=('Arial', 12))
        pin_entry.pack(pady=5)
        tk.Button(pin_win, text="Save", command=save_pin, width=10).pack(pady=5)
        pin_entry.focus_set()
        pin_win.grab_set()  # Make the window modal

    def prompt_pin_and_save(self, face_img, face_encoding):
        def check_pin():
            pin = pin_entry.get()
            try:
                with open("owner_pin.txt", "r") as f:
                    saved_pin = f.read().strip()
            except FileNotFoundError:
                saved_pin = None
                
            if pin == saved_pin:
                try:
                    # Save the new face image and encoding
                    cv2.imwrite(OWNER_FACE_PATH, face_img)
                    np.save('owner_face_encoding.npy', face_encoding)
                    
                    pin_win.destroy()
                    messagebox.showinfo("Success", "Owner's face has been updated.")
                    self.window.after(100, self.start_monitoring)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update: {str(e)}")
            else:
                messagebox.showerror("Error", "Incorrect PIN. Cannot update owner's face.")
                pin_win.lift()

        pin_win = tk.Toplevel(self.window)
        pin_win.title("Confirm Owner PIN")
        tk.Label(pin_win, text="Enter current 4-digit PIN:").pack(pady=5)
        pin_entry = tk.Entry(pin_win, show='*', width=10, font=('Arial', 12))
        pin_entry.pack(pady=5)
        tk.Button(pin_win, text="Confirm", command=check_pin, width=10).pack(pady=5)
        pin_entry.focus_set()
        pin_win.grab_set()  # Make the window modal

    def update(self):
        ret, frame = self.vid.read()
        if ret:
            try:
                # Store the original frame for snapshot
                self.last_frame = frame.copy()
                
                # Process the frame for display
                display_frame = cv2.flip(frame, 1)
                display_frame = cv2.resize(display_frame, (self.canvas_width, self.canvas_height))
                
                # Create a smaller frame for face detection (faster processing)
                small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
                
                # Detect faces with adjusted parameters
                faces = self.face_cascade.detectMultiScale(
                    gray, 
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(40, 40)  # Adjusted for smaller frame
                )
                
                self.face_in_box = False
                
                # Find the largest face
                largest_face = None
                max_area = 0
                for (x, y, w, h) in faces:
                    area = w * h
                    if area > max_area:
                        max_area = area
                        largest_face = (x, y, w, h)
                
                # Draw box if face is detected
                if largest_face is not None:
                    x, y, w, h = largest_face
                    # Scale up coordinates for display frame
                    x *= 2
                    y *= 2
                    w *= 2
                    h *= 2
                    
                    # Check if face is within the box
                    box_center_x = (self.box_x1 + self.box_x2) // 2
                    box_center_y = (self.box_y1 + self.box_y2) // 2
                    face_center_x = x + w // 2
                    face_center_y = y + h // 2
                    
                    if (box_center_x - w//2 <= face_center_x <= box_center_x + w//2 and
                        box_center_y - h//2 <= face_center_y <= box_center_y + h//2):
                        self.face_in_box = True
                        
                    # Draw the face box
                    cv2.rectangle(display_frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
                    
                # Draw the box on the display frame
                cv2.rectangle(display_frame, (self.box_x1, self.box_y1), 
                            (self.box_x2, self.box_y2), (0, 255, 0), 2)
                
                # Convert to PhotoImage and display
                photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)))
                self.canvas.create_image(0, 0, image=photo, anchor=tk.NW)
                self.canvas.photo = photo  # Keep a reference to prevent garbage collection
                
            except Exception as e:
                print(f"[DEBUG] Update error: {e}")
                
        self.window.after(self.delay, self.update)

    def on_closing(self):
        if self.vid.isOpened():
            self.vid.release()
        self.window.destroy()

def lock_computer():
    subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])

class MonitorApp:
    def __init__(self, window, window_title):
        self.window = window
        self.window.title(window_title)
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.video_source = 0
        self.vid = cv2.VideoCapture(self.video_source)
        self.canvas_width = 400
        self.canvas_height = 300
        self.canvas = tk.Canvas(window, width=self.canvas_width, height=self.canvas_height)
        self.canvas.pack()
        self.status_label = tk.Label(window, text="Monitoring for owner...")
        self.status_label.pack()
        self.owner_face_encoding = self.load_owner_face_encoding()
        self.last_seen_time = time.time()
        self.absent = False
        self.delay = 30
        self.update()
        self.window.mainloop()

    def update(self):
        try:
            ret, frame = self.vid.read()
            if not ret:
                self.window.after(self.delay, self.update)
                return
                
            # Flip the frame horizontally for a mirrored view
            frame = cv2.flip(frame, 1)
            
            # Create a smaller frame for face recognition (faster processing)
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_small_frame = small_frame[:, :, ::-1]  # Convert BGR to RGB
            
            # Find all face locations and encodings in the current frame
            face_locations = face_recognition.face_locations(rgb_small_frame)
            
            # Find the largest face
            largest_face = None
            max_area = 0
            for (top, right, bottom, left) in face_locations:
                area = (right - left) * (bottom - top)
                if area > max_area:
                    max_area = area
                    largest_face = (top, right, bottom, left)
            
            owner_detected = False
            
            # If a face is found, process it
            if largest_face is not None:
                top, right, bottom, left = largest_face
                
                # Scale up face coordinates to match original frame size
                top *= 2
                right *= 2
                bottom *= 2
                left *= 2
                
                # Get the face ROI (Region of Interest)
                face_roi = frame[top:bottom, left:right]
                if face_roi.size > 0:  # Ensure the ROI is valid
                    try:
                        # Convert the face ROI to RGB (dlib uses RGB)
                        rgb_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)
                        
                        # Get face landmarks for better encoding
                        face_landmarks = face_recognition.face_landmarks(rgb_face)
                        
                        if face_landmarks:  # If we got landmarks
                            # Encode the face using landmarks for better accuracy
                            face_encodings = face_recognition.face_encodings(
                                rgb_face, 
                                face_landmarks
                            )
                            
                            if face_encodings:  # If encoding was successful
                                # Compare with owner's encoding
                                match = face_recognition.compare_faces(
                                    [self.owner_face_encoding], 
                                    face_encodings[0], 
                                    tolerance=0.6  # Slightly higher tolerance for better matching
                                )
                                if match:  # Check if match list is not empty
                                    owner_detected = match[0]
                    except Exception as e:
                        print(f"[DEBUG] Face encoding error: {e}")
                
                # Draw face rectangle
                color = (0, 255, 0) if owner_detected else (0, 0, 255)  # Green if owner, red otherwise
                cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
                
                # Add label above the rectangle
                label = "Owner" if owner_detected else "Unknown"
                cv2.putText(frame, label, (left, top - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # Update status based on face detection
            current_time = time.time()
            if owner_detected:
                self.last_seen_time = current_time
                self.absent = False
                status_text = "Owner detected"
                status_color = (0, 255, 0)
            else:
                elapsed = current_time - self.last_seen_time
                status_text = f"Owner not detected: {elapsed:.1f}s"
                status_color = (0, 0, 255)
                
                if elapsed > 5 and not self.absent:
                    self.absent = True
                    self.status_label.config(text="Owner not detected: LOCKING")
                    self.window.update()
                    lock_computer()
            
            # Display status on the frame
            cv2.putText(frame, status_text, (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
            
            # Resize the frame to fit the canvas
            frame = cv2.resize(frame, (self.canvas_width, self.canvas_height))
            
            # Convert the frame to PhotoImage and display it
            self.photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            self.canvas.create_image(0, 0, image=self.photo, anchor=tk.NW)
            
        except Exception as e:
            print(f"[DEBUG] Exception in MonitorApp.update: {e}")
            
        # Schedule the next update
        self.window.after(self.delay, self.update)

    def load_owner_face_encoding(self):
        encoding_path = 'owner_face_encoding.npy'
        if not os.path.exists(OWNER_FACE_PATH) or not os.path.exists(encoding_path):
            messagebox.showerror("Error", "No registered owner face found. Please register first.")
            self.window.destroy()
            return None
            
        try:
            # Load the pre-computed face encoding
            face_encoding = np.load(encoding_path)
            return face_encoding
        except Exception as e:
            print(f"[DEBUG] Error loading face encoding: {e}")
            # Fallback to computing from image if encoding file is corrupted
            try:
                image = face_recognition.load_image_file(OWNER_FACE_PATH)
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                encodings = face_recognition.face_encodings(rgb_image)
                if encodings:
                    return encodings[0]
                else:
                    messagebox.showerror("Error", "Could not detect a face in the saved image.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process owner face image:\n{e}")
                
        self.window.destroy()
        return None

    def on_closing(self):
        if self.vid.isOpened():
            self.vid.release()
        self.window.destroy()

def main_menu():
    def launch_register():
        menu_win.destroy()
        root = tk.Tk()
        app = FaceRegisterApp(root, "Register Owner Face")
    def launch_monitor():
        menu_win.destroy()
        root = tk.Tk()
        app = MonitorApp(root, "Owner Presence Monitor")
    menu_win = tk.Tk()
    menu_win.title("FacialRecogPass Main Menu")
    tk.Label(menu_win, text="Choose Mode:").pack(pady=10)
    tk.Button(menu_win, text="Register Owner", command=launch_register, width=30).pack(pady=5)
    tk.Button(menu_win, text="Monitor & Auto-Lock", command=launch_monitor, width=30).pack(pady=5)
    menu_win.mainloop()

if __name__ == '__main__':
    main_menu()

