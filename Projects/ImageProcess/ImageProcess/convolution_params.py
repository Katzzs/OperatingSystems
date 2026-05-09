import tkinter as tk
import numpy as np
from tkinter import simpledialog, messagebox
import cv2
from PIL import Image

def get_kernel_from_string(kernel_str):
    try:
        # Convert a string like "1,2,1;0,0,0;-1,-2,-1" to a numpy array
        rows = kernel_str.strip().split(';')
        kernel = np.array([[float(num) for num in row.split(',')] for row in rows])
        return kernel
    except Exception as e:
        messagebox.showerror("Invalid Kernel", f"Could not parse kernel: {e}")
        return None

def apply_custom_convolution(image, kernel_str):
    kernel = get_kernel_from_string(kernel_str)
    if kernel is not None:
        img_np = np.array(image)
        result = cv2.filter2D(img_np, -1, kernel)
        return Image.fromarray(result)
    return image

def apply_custom_gaussian(image, ksize_str, sigma_str):
    try:
        ksize = int(ksize_str)
        sigma = float(sigma_str)
        if ksize % 2 == 0:
            ksize += 1  # kernel size must be odd
        img_np = np.array(image)
        result = cv2.GaussianBlur(img_np, (ksize, ksize), sigma)
        return Image.fromarray(result)
    except Exception as e:
        messagebox.showerror("Invalid Parameters", f"Could not apply Gaussian: {e}")
        return image
