import tkinter as tk
from tkinter import Menu, filedialog, Frame, messagebox, ttk, simpledialog
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageEnhance, ImageChops, ImageFilter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from skimage.filters import threshold_otsu
from adaptive_binarization import adaptive_binarize
from segmentation import select_and_segment
from convolution_params import apply_custom_convolution, apply_custom_gaussian

# Global Variables
original_image = None
modified_image = None
detector_window = None
detector_canvas = None
shape_count_label = None

# --- Image Handling Functions ---
def upload_image():
    """Loads an image from file and displays it safely."""
    global original_image, modified_image

    file_path = filedialog.askopenfilename()
    if not file_path:
        return

    try:
        original_image = Image.open(file_path).convert("RGB")  # Ensure RGB format
        modified_image = original_image.copy()  # Create a working copy
        display_image(modified_image)
        reset_sliders()  # Reset sliders when a new image is loaded
    except Exception as e:
        print(f"Error loading image: {e}")  # Print error to console (or show a popup)


def display_image(image):
    """Displays an image on the canvas, properly centered."""
    img_resized = image.resize((500, 500), Image.LANCZOS)
    img_tk = ImageTk.PhotoImage(img_resized)
    
    image_canvas.delete("all")  # Clear previous image
    image_canvas.create_image(275, 275, anchor="center", image=img_tk)  # Properly center image
    image_canvas.image = img_tk  # Prevent garbage collection

    # --- Rotation Functions ---
def rotate_image(degrees):
    """Rotate the image by the specified degrees (180 or 360)."""
    global modified_image

    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return

    # Rotate the image by the specified degrees
    rotated_image = modified_image.rotate(degrees)

    # Update the displayed image
    display_image(rotated_image)

    # Update the working image to the rotated version
    modified_image = rotated_image

def open_shape_color_detector():
    """Opens a new window for the Shape & Color Detector."""
    global detector_window, detector_canvas, shape_count_label

    detector_window = tk.Toplevel(root)
    detector_window.title("Shape & Color Detector")
    detector_window.geometry("800x600")
    
    # Store image reference at window level to prevent garbage collection
    detector_window.image_displayed = None
    
    # --- Menu Bar ---
    menu_bar = Menu(detector_window)
    detector_window.config(menu=menu_bar)
    
    file_menu = Menu(menu_bar, tearoff=False)
    menu_bar.add_cascade(label="File", menu=file_menu)
    
    # Create a single frame for all UI elements
    main_frame = tk.Frame(detector_window)
    main_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
    
    # Create canvas for displaying results
    detector_canvas = tk.Canvas(main_frame, width=600, height=400, bg="white", borderwidth=2, relief="solid")
    detector_canvas.pack(pady=10)
    
    # Shape count label
    shape_count_label = tk.Label(main_frame, text="Triangles: 0 | Circles: 0", font=("Arial", 14))
    shape_count_label.pack(pady=5)
    
    # Return button
    return_button = tk.Button(main_frame, text="Return to Main Window", font=("Arial", 14),
                            command=detector_window.destroy)
    return_button.pack(pady=10)

    file_menu.add_command(label="Open", command=detect_shapes)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=detector_window.destroy)

def detect_shapes():
    file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")])
    if not file_path:
        return

    image = cv2.imread(file_path)
    if image is None:
        messagebox.showerror("Error", "Unable to load image")
        return

    working_image = image.copy()
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Apply Gaussian Blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive Thresholding
    thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 11, 2)

    # Apply high contrast
    contrast_enhancer = ImageEnhance.Contrast(Image.fromarray(thresh))
    high_contrast_image = contrast_enhancer.enhance(2)
    thresh = np.array(high_contrast_image)

    # Morphological operation to remove small noise
    kernel = np.ones((3, 3), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Store detected shapes
    shape_counts = {}
    color_counts = {}

    def detect_color(mask):
        """Detects the dominant color in the given mask, including shades."""
    
        COLOR_RANGES = {
            "Red": [(0, 150, 100), (10, 255, 255), (170, 150, 100), (180, 255, 255)],  
            "Green": [(35, 50, 50), (85, 255, 255)],  
            "Blue": [(90, 50, 50), (130, 255, 255)],
            "Yellow": [(20, 100, 100), (30, 255, 255)],
            "Cyan": [(80, 100, 100), (90, 255, 255)],
            "Magenta": [(140, 100, 100), (160, 255, 255)],
            "Orange": [(10, 100, 100), (20, 255, 255)],
            "Purple": [(130, 50, 50), (160, 255, 255)],
            "Brown": [(10, 100, 20), (20, 255, 200)],
            "Indigo": [(130, 50, 50), (145, 255, 255)],
            "Violet": [(145, 50, 50), (160, 255, 255)]
        }

        max_pixels = 0
        detected_color = None

        for color, ranges in COLOR_RANGES.items():
            color_mask = cv2.inRange(hsv, ranges[0], ranges[1])
            if len(ranges) == 4:
                color_mask += cv2.inRange(hsv, ranges[2], ranges[3])
            
            overlap = cv2.bitwise_and(color_mask, mask)
            pixels = np.sum(overlap > 0)

            if pixels > max_pixels:
                max_pixels = pixels
                detected_color = color

        return detected_color   

    # **Dynamic Small Shape Filtering**
    min_area_threshold = max(100, 0.0005 * (image.shape[0] * image.shape[1]))

    # **Shape Detection**
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area_threshold:  # Ignore small noise
            continue

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

        # Create mask for color detection
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.drawContours(mask, [approx], -1, 255, thickness=cv2.FILLED)

        # **Shape Classification**
        num_sides = len(approx)

        # **Refined Circularity Check**
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
        if circularity > 0.85 and num_sides > 6:  
            shape = "Circle"
        elif 0.5 < circularity <= 0.85 and num_sides > 6:
            shape = "Ellipse"
        elif num_sides == 3:
            shape = "Triangle"
        elif num_sides == 4:
            x, y, w, h = cv2.boundingRect(approx)
            aspect_ratio = float(w) / h
            if 0.85 <= aspect_ratio <= 1.15:
                shape = "Square"
            else:
                # Check for diamond shape
                angles = []
                for i in range(4):
                    p1 = approx[i][0]
                    p2 = approx[(i + 1) % 4][0]
                    p3 = approx[(i + 2) % 4][0]
                    v1 = p2 - p1
                    v2 = p3 - p2
                    angle = np.arccos(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
                    angles.append(np.degrees(angle))
                if all(654 <= angle <= 85 for angle in angles):
                    shape = "Diamond"
                else:
                    shape = "Rectangle"
        elif num_sides == 5:
            shape = "Pentagon"
        elif num_sides == 6:
            shape = "Hexagon"
        elif num_sides == 10:
            shape = "Star"
        else:
            continue  # Skip unclassified shapes

        # Store shape count
        shape_counts[shape] = shape_counts.get(shape, 0) + 1
        cv2.drawContours(working_image, [approx], 0, (0, 255, 0), 2)

        # **Enhanced Label Placement & Size**
        M = cv2.moments(contour)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
            
            label_x = max(10, min(cX - 25, working_image.shape[1] - 100))
            label_y = max(20, min(cY, working_image.shape[0] - 20))

            cv2.putText(working_image, shape, (label_x, label_y), cv2.FONT_HERSHEY_SIMPLEX, 
                        0.6, (0, 0, 0), 2, cv2.LINE_AA)  # **Slightly Larger Text**

        # **Color Detection**
        detected_color = detect_color(mask)
        if detected_color:
            color_counts[detected_color] = color_counts.get(detected_color, 0) + 1

    # **Update Count Label**
    shape_text = " | ".join([f"{shape}: {count}" for shape, count in shape_counts.items()])
    color_text = " | ".join([f"{color}: {count}" for color, count in color_counts.items()])
    shape_count_label.config(text=f"{shape_text}\n{color_text}")

    # **Display Image in Tkinter**
    canvas_width, canvas_height = 600, 400
    img_display = cv2.cvtColor(working_image, cv2.COLOR_BGR2RGB)
    img_pil = Image.fromarray(img_display)

    img_pil.thumbnail((canvas_width, canvas_height), Image.LANCZOS)
    img_tk = ImageTk.PhotoImage(img_pil)

    detector_window.image_displayed = img_tk
    detector_canvas.delete("all")
    detector_canvas.create_image(canvas_width // 2, canvas_height // 2, anchor="center", image=detector_window.image_displayed)


def return_to_main_window(current_window):
    """Closes the Shape & Color Detector window and reopens the main window."""
    current_window.destroy()  # Close the detector window

    root.mainloop()

def apply_filter(filter_func):
    """Applies a selected filter to the image."""
    global modified_image
    if original_image:
        modified_image = filter_func(original_image.copy())  # Always apply filter to original
        display_image(modified_image)
        reset_sliders()  # Reset sliders when a filter is applied

def undo_changes():
    """Restores the original uploaded image."""
    global modified_image
    if original_image:
        modified_image = original_image.copy()
        display_image(modified_image)
        reset_sliders()

# --- Filter Functions ---
def tint_image(img, r_factor=1.0, g_factor=1.0, b_factor=1.0):
    """Applies a color tint to an image."""
    r, g, b = img.split()
    return Image.merge("RGB", (
        r.point(lambda p: p * r_factor), 
        g.point(lambda p: p * g_factor), 
        b.point(lambda p: p * b_factor)
    ))

def sepia(img):
    """Applies a sepia effect."""
    sepia_pixels = [
        (min(int(0.393 * r + 0.769 * g + 0.189 * b), 255),
         min(int(0.349 * r + 0.686 * g + 0.168 * b), 255),
         min(int(0.272 * r + 0.534 * g + 0.131 * b), 255))
        for r, g, b in img.getdata()
    ]
    img.putdata(sepia_pixels)
    return img

def grayscale(img, threshold=None):
    """Converts image to grayscale or black & white using Otsu's binarization."""
    img = img.convert("L")  # Convert to grayscale

    if threshold is None:
        return img  # Return standard grayscale image

    img_np = np.array(img)

    # Apply Otsu's threshold
    if threshold == "otsu":
        threshold = threshold_otsu(img_np) * 1.1  # Slightly increase threshold

    binarized_img = Image.fromarray((img_np > threshold).astype(np.uint8) * 255)  # Convert to binary image
    return binarized_img

# Dictionary to store filters for easy lookup
filters = {
    "Red Tint": lambda img: tint_image(img, 1.0, 0.6, 0.6),
    "Green Tint": lambda img: tint_image(img, 0.6, 1.0, 0.6),
    "Blue Tint": lambda img: tint_image(img, 0.6, 0.6, 1.0),
    "Sepia": sepia,
    "Negative": lambda img: ImageChops.invert(img),
    "Cyanotype": lambda img: tint_image(img, 0.3, 0.6, 1.0),
    "Warm Tone": lambda img: ImageEnhance.Color(img).enhance(1.3),
    "Cool Tone": lambda img: tint_image(img, 0.8, 0.9, 1.2),
    "High Contrast": lambda img: ImageEnhance.Contrast(img).enhance(2),
    "Low Contrast": lambda img: ImageEnhance.Contrast(img).enhance(0.5),
    "Grayscale": lambda img: grayscale(img),
    "Black and White": lambda img: grayscale(img, "otsu")  # Otsu's binarization applied
}

# --- Sidebar for RGB & Image Enhancement ---
def update_image():
    """Applies real-time changes to the image from sliders, including opacity."""
    if not original_image:
        return

    # Apply RGB adjustment
    adjusted_img = tint_image(original_image.copy(), r_var.get(), g_var.get(), b_var.get())

    # Apply image enhancements
    enhancer = ImageEnhance.Brightness(adjusted_img)
    adjusted_img = enhancer.enhance(brightness_var.get())

    enhancer = ImageEnhance.Contrast(adjusted_img)
    adjusted_img = enhancer.enhance(contrast_var.get())

    enhancer = ImageEnhance.Color(adjusted_img)
    adjusted_img = enhancer.enhance(saturation_var.get())

    enhancer = ImageEnhance.Sharpness(adjusted_img)
    blur_amount = blur_var.get() * 5  # Scale slider from 0-2 to 0-10
    adjusted_img = adjusted_img.filter(ImageFilter.GaussianBlur(blur_amount))

    # Apply opacity
    if adjusted_img.mode != "RGBA":
        adjusted_img = adjusted_img.convert("RGBA")  # Ensure image has an alpha channel

    alpha = int(255 * opacity_var.get())  # Scale opacity (0.0 - 2.0) to (0 - 255)
    alpha = max(0, min(255, alpha))  # Ensure valid range
    alpha_channel = Image.new("L", adjusted_img.size, alpha)  # Create alpha mask
    adjusted_img.putalpha(alpha_channel)  # Apply opacity

    display_image(adjusted_img)

def reset_sliders():
    """Resets all sliders to default values."""
    r_var.set(1.0)
    g_var.set(1.0)
    b_var.set(1.0)
    brightness_var.set(1.0)
    contrast_var.set(1.0)
    saturation_var.set(1.0)
    blur_var.set(1.0)

# --- GUI Setup ---
root = tk.Tk()
root.title("Image Processor")
root.geometry("1000x700")

# Set Application Icon
try:
    icon_img = tk.PhotoImage(file="icon.png")  
    root.wm_iconphoto(True, icon_img)
except:
    pass  # Ignore if icon not found

# Menu Bar
menu_bar = Menu(root)
root.config(menu=menu_bar)

# File Menu
file_menu = Menu(menu_bar, tearoff=False)
menu_bar.add_cascade(label="File", menu=file_menu)

# --- Image Process Menu ---
def handle_adaptive_binarization():
    global modified_image
    if original_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    # Dropdown for method
    def on_select():
        method = var.get()
        win.destroy()
        result = adaptive_binarize(original_image, method=method)
        modified_image = result
        display_image(modified_image)
    win = tk.Toplevel(root)
    win.title("Adaptive Method")
    tk.Label(win, text="Choose adaptive method:").pack(padx=10, pady=5)
    var = tk.StringVar(value="mean")
    opt = tk.OptionMenu(win, var, "mean", "gaussian")
    opt.pack(padx=10, pady=5)
    tk.Button(win, text="OK", command=on_select).pack(pady=10)
    win.grab_set()

from segmentation import select_and_segment

def handle_segmentation():
    global modified_image
    if original_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    def on_select():
        method = var.get()
        win.destroy()
        params = {}
        if method == "kmeans":
            k = tk.simpledialog.askinteger("K-means", "Number of clusters (k):", initialvalue=2, minvalue=2, maxvalue=10)
            params["k"] = k if k else 2
        elif method == "canny":
            low = tk.simpledialog.askinteger("Canny Edge", "Low threshold:", initialvalue=100, minvalue=0, maxvalue=255)
            high = tk.simpledialog.askinteger("Canny Edge", "High threshold:", initialvalue=200, minvalue=0, maxvalue=255)
            params["low"] = low if low is not None else 100
            params["high"] = high if high is not None else 200
        try:
            result = select_and_segment(original_image, method, **params)
            modified_image = result
            display_image(modified_image)
        except Exception as e:
            messagebox.showerror("Segmentation Error", str(e))
    win = tk.Toplevel(root)
    win.title("Segmentation Method")
    tk.Label(win, text="Choose segmentation method:").pack(padx=10, pady=5)
    var = tk.StringVar(value="kmeans")
    opt = tk.OptionMenu(win, var, "kmeans", "watershed", "otsu", "canny")
    opt.pack(padx=10, pady=5)
    tk.Button(win, text="OK", command=on_select).pack(pady=10)
    win.grab_set()

image_process_menu = Menu(menu_bar, tearoff=False)
menu_bar.add_cascade(label="Image Process", menu=image_process_menu)
image_process_menu.add_command(label="Adaptive Binarization", command=handle_adaptive_binarization)
image_process_menu.add_command(label="Segmentation", command=handle_segmentation)
file_menu.add_command(label="Open", command=upload_image)
file_menu.add_command(label="Undo", command=undo_changes)
file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

# Filters Menu
filters_menu = Menu(menu_bar, tearoff=False)
menu_bar.add_cascade(label="Filters", menu=filters_menu)

# Image Edit menu
image_editing_menu = Menu(menu_bar, tearoff=False)
menu_bar.add_cascade(label="Image Editing", menu=image_editing_menu)

# --- Convolution Menu ---
def handle_smooth():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    clear_convolution_controls()
    tk.Label(convolution_control_frame, text="Smooth (Average Blur)").pack(anchor="w")
    tk.Label(convolution_control_frame, text="Kernel Size (odd integer):").pack(anchor="w")
    ksize_entry = tk.Entry(convolution_control_frame, width=10)
    ksize_entry.insert(0, "3")
    ksize_entry.pack(anchor="w")
    def apply():
        try:
            k = int(ksize_entry.get())
            if k % 2 == 0:
                k += 1
            img_np = np.array(modified_image)
            kernel = np.ones((k, k), np.float32) / (k * k)
            smoothed = cv2.filter2D(img_np, -1, kernel)
            globals()["modified_image"] = Image.fromarray(smoothed)
            display_image(modified_image)
        except Exception as e:
            messagebox.showerror("Invalid Input", str(e))
    tk.Button(convolution_control_frame, text="Apply", command=apply).pack(pady=5)
    show_convolution_controls()

def handle_gaussian_blur():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    clear_convolution_controls()
    tk.Label(convolution_control_frame, text="Gaussian Blur").pack(anchor="w")
    tk.Label(convolution_control_frame, text="Kernel Size (odd integer):").pack(anchor="w")
    ksize_entry = tk.Entry(convolution_control_frame, width=10)
    ksize_entry.insert(0, "15")
    ksize_entry.pack(anchor="w")
    tk.Label(convolution_control_frame, text="Sigma:").pack(anchor="w")
    sigma_entry = tk.Entry(convolution_control_frame, width=10)
    sigma_entry.insert(0, "5.0")
    sigma_entry.pack(anchor="w")
    def apply():
        try:
            k = int(ksize_entry.get())
            if k % 2 == 0:
                k += 1
            sigma = float(sigma_entry.get())
            img_np = np.array(modified_image)
            gaussian = cv2.GaussianBlur(img_np, (k, k), sigma)
            globals()["modified_image"] = Image.fromarray(gaussian)
            display_image(modified_image)
        except Exception as e:
            messagebox.showerror("Invalid Input", str(e))
    tk.Button(convolution_control_frame, text="Apply", command=apply).pack(pady=5)
    show_convolution_controls()

def handle_mean_removal():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    clear_convolution_controls()
    tk.Label(convolution_control_frame, text="Mean Removal Kernel (rows with ';', values with ','):").pack(anchor="w")
    kernel_entry = tk.Entry(convolution_control_frame, width=50)
    kernel_entry.insert(0, "-1,-1,-1;-1,9,-1;-1,-1,-1")
    kernel_entry.pack(anchor="w")
    def apply():
        from convolution_params import get_kernel_from_string
        kernel_str = kernel_entry.get()
        kernel = get_kernel_from_string(kernel_str)
        if kernel is not None:
            img_np = np.array(modified_image)
            mean_removed = cv2.filter2D(img_np, -1, kernel)
            globals()["modified_image"] = Image.fromarray(mean_removed)
            display_image(modified_image)
    tk.Button(convolution_control_frame, text="Apply", command=apply).pack(pady=5)
    show_convolution_controls()

def handle_sharpen():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    clear_convolution_controls()
    tk.Label(convolution_control_frame, text="Sharpen Kernel (rows with ';', values with ','):").pack(anchor="w")
    kernel_entry = tk.Entry(convolution_control_frame, width=50)
    kernel_entry.insert(0, "0,-1,0;-1,5,-1;0,-1,0")
    kernel_entry.pack(anchor="w")
    def apply():
        from convolution_params import get_kernel_from_string
        kernel_str = kernel_entry.get()
        kernel = get_kernel_from_string(kernel_str)
        if kernel is not None:
            img_np = np.array(modified_image)
            sharpened = cv2.filter2D(img_np, -1, kernel)
            globals()["modified_image"] = Image.fromarray(sharpened)
            display_image(modified_image)
    tk.Button(convolution_control_frame, text="Apply", command=apply).pack(pady=5)
    show_convolution_controls()

def handle_emboss():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    clear_convolution_controls()
    tk.Label(convolution_control_frame, text="Emboss Kernel (rows with ';', values with ','):").pack(anchor="w")
    kernel_entry = tk.Entry(convolution_control_frame, width=50)
    kernel_entry.insert(0, "-2,-1,0;-1,1,1;0,1,2")
    kernel_entry.pack(anchor="w")
    def apply():
        from convolution_params import get_kernel_from_string
        kernel_str = kernel_entry.get()
        kernel = get_kernel_from_string(kernel_str)
        if kernel is not None:
            img_np = np.array(modified_image)
            embossed = cv2.filter2D(img_np, -1, kernel)
            globals()["modified_image"] = Image.fromarray(embossed)
            display_image(modified_image)
    tk.Button(convolution_control_frame, text="Apply", command=apply).pack(pady=5)
    show_convolution_controls()

convolution_menu = Menu(menu_bar, tearoff=False)
menu_bar.add_cascade(label="Convolution", menu=convolution_menu)
convolution_menu.add_command(label="Smooth", command=handle_smooth)
convolution_menu.add_command(label="Gaussian Blur", command=handle_gaussian_blur)
convolution_menu.add_command(label="Mean Removal", command=handle_mean_removal)
convolution_menu.add_command(label="Sharpen", command=handle_sharpen)
convolution_menu.add_command(label="Emboss", command=handle_emboss)

# --- Handlers for custom convolution menu items ---
def handle_custom_kernel():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    clear_convolution_controls()
    tk.Label(convolution_control_frame, text="Custom Kernel (rows with ';', values with ','):" ).pack(anchor="w")
    kernel_entry = tk.Entry(convolution_control_frame, width=50)
    kernel_entry.insert(0, "-1,-1,-1;0,9,0;-1,-1,-1")
    kernel_entry.pack(anchor="w")
    def apply():
        kernel_str = kernel_entry.get()
        new_img = apply_custom_convolution(modified_image, kernel_str)
        if new_img:
            globals()["modified_image"] = new_img
            display_image(new_img)
    tk.Button(convolution_control_frame, text="Apply", command=apply).pack(pady=5)
    show_convolution_controls()



# Add custom convolution submenu
custom_conv_menu = Menu(convolution_menu, tearoff=False)
convolution_menu.add_cascade(label="Custom Kernel",  command=handle_custom_kernel)


# --- Submenu control frames ---
mirror_frame = tk.Frame(root)
translation_frame = tk.Frame(root)
histogram_frame = tk.Frame(root)
binary_proj_frame = tk.Frame(root)

# --- Convolution Control Frame ---
convolution_control_frame = tk.Frame(root, bd=2, relief="groove", padx=10, pady=10)
convolution_control_frame.pack_forget()  # Hide by default

# Helper to clear frame
def clear_convolution_controls():
    for widget in convolution_control_frame.winfo_children():
        widget.destroy()

def hide_convolution_controls():
    convolution_control_frame.pack_forget()

def show_convolution_controls():
    hide_all_editing_frames()
    convolution_control_frame.pack(pady=(15, 0), fill="x")

# --- Handlers for menu items ---
def handle_custom_kernel():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    clear_convolution_controls()
    tk.Label(convolution_control_frame, text="Custom Kernel (rows with ';', values with ','):").pack(anchor="w")
    kernel_entry = tk.Entry(convolution_control_frame, width=50)
    kernel_entry.insert(0, "-1,-1,-1;0,9,0;-1,-1,-1")
    kernel_entry.pack(anchor="w")
    def apply():
        kernel_str = kernel_entry.get()
        new_img = apply_custom_convolution(modified_image, kernel_str)
        if new_img:
            globals()["modified_image"] = new_img
            display_image(new_img)
    tk.Button(convolution_control_frame, text="Apply", command=apply).pack(pady=5)
    show_convolution_controls()

def handle_custom_gaussian():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    clear_convolution_controls()
    tk.Label(convolution_control_frame, text="Gaussian Kernel Size (odd integer):").pack(anchor="w")
    ksize_entry = tk.Entry(convolution_control_frame, width=10)
    ksize_entry.insert(0, "15")
    ksize_entry.pack(anchor="w")
    tk.Label(convolution_control_frame, text="Sigma:").pack(anchor="w")
    sigma_entry = tk.Entry(convolution_control_frame, width=10)
    sigma_entry.insert(0, "5.0")
    sigma_entry.pack(anchor="w")
    def apply():
        ksize_str = ksize_entry.get()
        sigma_str = sigma_entry.get()
        new_img = apply_custom_gaussian(modified_image, ksize_str, sigma_str)
        if new_img:
            globals()["modified_image"] = new_img
            display_image(new_img)
    tk.Button(convolution_control_frame, text="Apply", command=apply).pack(pady=5)
    show_convolution_controls()

# Update menu to use new handlers
# Use custom_conv_menu if you need to update submenu commands dynamically:
# custom_conv_menu.entryconfig("Custom Kernel", command=handle_custom_kernel)
# custom_conv_menu.entryconfig("Custom Gaussian Blur", command=handle_custom_gaussian)

# --- Show/hide logic for each submenu ---
def hide_all_editing_frames():
    rotation_frame.pack_forget()
    mirror_frame.pack_forget()
    translation_frame.pack_forget()
    histogram_frame.pack_forget()
    binary_proj_frame.pack_forget()

def show_rotation_controls():
    hide_all_editing_frames()
    rotation_frame.pack(pady=(15, 0))

def show_mirror_controls():
    hide_all_editing_frames()
    mirror_frame.pack(pady=(15, 0))

def show_translation_controls():
    hide_all_editing_frames()
    translation_frame.pack(pady=(15, 0))

def show_histogram_controls():
    hide_all_editing_frames()
    histogram_frame.pack(pady=(15, 0))

def show_binary_proj_controls():
    hide_all_editing_frames()
    binary_proj_frame.pack(pady=(15, 0))

# --- Image Editing menu ---
# Rotate submenu
image_editing_menu.add_command(label="Rotate", command=show_rotation_controls)
# Mirror submenu
image_editing_menu.add_command(label="Mirror", command=show_mirror_controls)
# Translation submenu
image_editing_menu.add_command(label="Translate", command=show_translation_controls)
# Histogram submenu
image_editing_menu.add_command(label="Histogram", command=show_histogram_controls)
# Binary Image Projection submenu
image_editing_menu.add_command(label="Binary Image Projection", command=show_binary_proj_controls)

# Grayscale & Black and White
filters_menu.add_command(label="Grayscale", command=lambda: apply_filter(filters["Grayscale"]))
filters_menu.add_command(label="Black and White", command=lambda: apply_filter(filters["Black and White"]))

# Colors Submenu
colors_menu = Menu(filters_menu, tearoff=False)
filters_menu.add_cascade(label="Colors", menu=colors_menu)

# Add Filters Dynamically
for filter_name, filter_func in filters.items():
    if filter_name not in ["Grayscale", "Black and White"]:
        colors_menu.add_command(label=filter_name, command=lambda f=filter_func: apply_filter(f))


# --- Sidebar Frame ---
sidebar = Frame(root, width=250, relief="solid", borderwidth=2)
sidebar.pack(side="right", fill="y", padx=10, pady=10)

# --- Thresholding & Segmentation Section ---
threshold_frame = tk.LabelFrame(sidebar, text="Thresholding & Segmentation", padx=10, pady=10)
threshold_frame.pack(fill="x", padx=5, pady=5)

threshold_mode = tk.StringVar(value="average")  # "average" or "dual"

def apply_threshold(_=None):
    global modified_image
    if not original_image:
        return

    img_gray = original_image.convert("L")
    img_np = np.array(img_gray)

    if threshold_mode.get() == "average":
        t = int(threshold1.get())
        _, thresh_img = cv2.threshold(img_np, t, 255, cv2.THRESH_BINARY_INV)
    else:
        t1 = int(threshold1.get())
        t2 = int(threshold2.get())
        if t1 > t2:
            t1, t2 = t2, t1
        mask = cv2.inRange(img_np, t1, t2)
        thresh_img = np.where(mask > 0, 255, 0).astype(np.uint8)

    modified_image = Image.fromarray(thresh_img)
    display_image(modified_image)

def switch_threshold_mode():
    if threshold_mode.get() == "average":
        threshold_mode.set("dual")
        toggle_button.config(text="Switch to Average Thresholding")
        slider2_label.pack()
        slider2.pack()
    else:
        threshold_mode.set("average")
        toggle_button.config(text="Switch to Dual Thresholding")
        slider2_label.pack_forget()
        slider2.pack_forget()
    apply_threshold()

toggle_button = tk.Button(threshold_frame, text="Switch to Dual Thresholding", command=switch_threshold_mode)
toggle_button.pack(fill="x", pady=5)

# Threshold 1
slider1_label = tk.Label(threshold_frame, text="Threshold 1:")
slider1_label.pack()
threshold1 = tk.DoubleVar(value=127)
slider1 = tk.Scale(threshold_frame, from_=0, to=255, orient="horizontal", variable=threshold1, command=apply_threshold)
slider1.pack()

# Threshold 2
slider2_label = tk.Label(threshold_frame, text="Threshold 2:")
threshold2 = tk.DoubleVar(value=127)
slider2 = tk.Scale(threshold_frame, from_=0, to=255, orient="horizontal", variable=threshold2, command=apply_threshold)
slider2_label.pack_forget()
slider2.pack_forget()


# Create slider variables
r_var, g_var, b_var = tk.DoubleVar(value=1.0), tk.DoubleVar(value=1.0), tk.DoubleVar(value=1.0)
brightness_var = tk.DoubleVar(value=1.0)
contrast_var = tk.DoubleVar(value=1.0)
saturation_var = tk.DoubleVar(value=1.0)
blur_var = tk.DoubleVar(value=1.0)
opacity_var = tk.DoubleVar(value=1.0)

# Create UI sliders
enhancements = [
    ("Red", r_var), ("Green", g_var), ("Blue", b_var),
    ("Brightness", brightness_var), ("Contrast", contrast_var),
    ("Saturation", saturation_var), ("Blur", blur_var),
    ("Opacity", opacity_var)  # NEW: Opacity slider added
]
for label, var in enhancements:
    tk.Label(sidebar, text=label).pack()
    tk.Scale(sidebar, from_=0.0, to=2.0, resolution=0.1, orient="horizontal", variable=var, command=lambda x: update_image()).pack()


 # Shape & Color Detector Button
tk.Button(sidebar, text="Shape & Color Detector", fg="red", bg="black", font=("Arial", 12,),
          command=open_shape_color_detector).pack(pady=20)

# --- Rotation Controls ---
rotation_frame = tk.Frame(root)
# Initially hidden; pack only when Rotate is selected
# rotation_frame.pack(pady=(15, 0))

# --- Mirror Controls ---
mirror_label = tk.Label(mirror_frame, text="Mirror image:")
mirror_label.pack(side="left", padx=(0, 5))
def mirror_vertical():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    mirrored = modified_image.transpose(Image.FLIP_TOP_BOTTOM)
    display_image(mirrored)
    modified_image = mirrored

def mirror_horizontal():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    mirrored = modified_image.transpose(Image.FLIP_LEFT_RIGHT)
    display_image(mirrored)
    modified_image = mirrored

vertical_btn = tk.Button(mirror_frame, text="Vertical Mirror", command=mirror_vertical)
horizontal_btn = tk.Button(mirror_frame, text="Horizontal Mirror", command=mirror_horizontal)
vertical_btn.pack(side="left", padx=(5, 0))
horizontal_btn.pack(side="left", padx=(5, 0))

# --- Translation Controls ---
translation_label = tk.Label(translation_frame, text="Translate (x, y):")
translation_label.pack(side="left", padx=(0, 5))
trans_x_var = tk.StringVar(value="0")
trans_y_var = tk.StringVar(value="0")
trans_x_entry = tk.Entry(translation_frame, textvariable=trans_x_var, width=5)
trans_y_entry = tk.Entry(translation_frame, textvariable=trans_y_var, width=5)
trans_x_entry.pack(side="left")
trans_y_entry.pack(side="left")
def translate_image():
    global modified_image
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    try:
        dx = int(trans_x_var.get())
        dy = int(trans_y_var.get())
    except ValueError:
        messagebox.showerror("Invalid Input", "Enter integer values for x and y.")
        return
    arr = np.array(modified_image)
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    shifted = cv2.warpAffine(arr, M, (arr.shape[1], arr.shape[0]))
    shifted_img = Image.fromarray(shifted)
    display_image(shifted_img)
    modified_image = shifted_img

translate_btn = tk.Button(translation_frame, text="Translate", command=translate_image)
translate_btn.pack(side="left", padx=(5, 0))

# --- Histogram Controls ---
histogram_label = tk.Label(histogram_frame, text="Show RGB Histogram")
histogram_label.pack(side="left", padx=(0, 5))
def show_histogram_window():
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    img = np.array(modified_image)
    win = tk.Toplevel(root)
    win.title("RGB Histogram")
    win.geometry("600x400")
    matplotlib.use('Agg')
    fig, ax = plt.subplots(3, 1, figsize=(6, 4), sharex=True)
    colors = ('r', 'g', 'b')
    for i, color in enumerate(colors):
        ax[i].hist(img[..., i].flatten(), bins=256, color=color, alpha=0.7)
        ax[i].set_ylabel(color.upper())
    ax[2].set_xlabel('Pixel Value')
    fig.tight_layout()
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

histogram_btn = tk.Button(histogram_frame, text="Show Histogram", command=show_histogram_window)
histogram_btn.pack(side="left", padx=(5, 0))

# --- Binary Image Projection Controls ---
def show_binary_projection_window():
    if modified_image is None:
        messagebox.showwarning("No Image", "Please load an image first!")
        return
    img = np.array(modified_image.convert("L"))
    # Binarize the image (0 or 1)
    binary = (img > 127).astype(np.uint8)
    vert_proj = np.sum(binary, axis=0)
    hori_proj = np.sum(binary, axis=1)

    win = tk.Toplevel(root)
    win.title("Binary Image Projection")
    win.geometry("900x400")
    fig, ax = plt.subplots(1, 3, figsize=(12, 4))

    # Show the binary image (left)
    ax[0].imshow(binary, cmap='gray', interpolation='nearest')
    ax[0].set_title('Binary Image')
    ax[0].axis('off')

    # Horizontal projection (bottom bar plot)
    ax[1].barh(range(len(hori_proj)), hori_proj, color='black')
    ax[1].invert_yaxis()
    ax[1].set_title('Horizontal Projection')
    ax[1].set_xlabel('Count of 1-pixels')
    ax[1].set_ylabel('Row')

    # Vertical projection (right bar plot)
    ax[2].bar(range(len(vert_proj)), vert_proj, color='black')
    ax[2].set_title('Vertical Projection')
    ax[2].set_xlabel('Column')
    ax[2].set_ylabel('Count of 1-pixels')

    fig.tight_layout()
    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)


binary_proj_btn = tk.Button(binary_proj_frame, text="Show Binary Projection", command=show_binary_projection_window)
binary_proj_btn.pack(side="left", padx=(5, 0))

binary_proj_label = tk.Label(binary_proj_frame, text="Show Binary Image Projection")
binary_proj_label.pack(side="left", padx=(0, 5))




rotation_label = tk.Label(rotation_frame, text="Rotate (degrees):")
rotation_label.pack(side="left", padx=(0, 5))

rotation_var = tk.StringVar(value="0")
rotation_entry = tk.Entry(rotation_frame, textvariable=rotation_var, width=5)
rotation_entry.pack(side="left")

def on_rotate_button():
    try:
        deg = float(rotation_var.get())
        rotate_image(deg)
    except ValueError:
        messagebox.showerror("Invalid Input", "Please enter a valid number for degrees.")

rotate_btn = tk.Button(rotation_frame, text="Rotate", command=on_rotate_button)
rotate_btn.pack(side="left", padx=(5, 0))

# Image Canvas
image_canvas = tk.Canvas(root, width=550, height=550, bg="lightgray", borderwidth=3, relief="solid")
image_canvas.pack(pady=20)

# Run Application
root.mainloop()



