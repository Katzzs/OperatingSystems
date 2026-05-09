import cv2
import numpy as np
from PIL import Image

def adaptive_binarize(pil_img, method='mean', block_size=11, C=2):
    """
    Applies adaptive binarization to a PIL image.
    method: 'mean' or 'gaussian'
    block_size: Size of the neighborhood area.
    C: Constant subtracted from the mean/weighted mean.
    Returns a binarized PIL image.
    """
    img_gray = pil_img.convert('L')
    img_np = np.array(img_gray)
    if method == 'mean':
        thresh = cv2.adaptiveThreshold(img_np, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, block_size, C)
    else:
        thresh = cv2.adaptiveThreshold(img_np, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, C)
    return Image.fromarray(thresh)
