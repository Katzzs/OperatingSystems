import cv2
import numpy as np
from PIL import Image

def kmeans_segmentation(pil_img, k=2):
    """
    Segments the image using k-means clustering on color.
    """
    img_np = np.array(pil_img.convert('RGB'))
    Z = img_np.reshape((-1,3))
    Z = np.float32(Z)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _,label,center=cv2.kmeans(Z,k,None,criteria,10,cv2.KMEANS_RANDOM_CENTERS)
    center = np.uint8(center)
    res = center[label.flatten()]
    segmented_img = res.reshape((img_np.shape))
    return Image.fromarray(segmented_img)

def watershed_segmentation(pil_img):
    """
    Segments the image using the watershed algorithm.
    """
    img = np.array(pil_img.convert('RGB'))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    ret, thresh = cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    # noise removal
    kernel = np.ones((3,3),np.uint8)
    opening = cv2.morphologyEx(thresh,cv2.MORPH_OPEN,kernel,iterations = 2)
    # sure background area
    sure_bg = cv2.dilate(opening,kernel,iterations=3)
    # Finding sure foreground area
    dist_transform = cv2.distanceTransform(opening,cv2.DIST_L2,5)
    ret, sure_fg = cv2.threshold(dist_transform,0.7*dist_transform.max(),255,0)
    # Finding unknown region
    sure_fg = np.uint8(sure_fg)
    unknown = cv2.subtract(sure_bg,sure_fg)
    # Marker labelling
    ret, markers = cv2.connectedComponents(sure_fg)
    # Add one to all labels so that sure background is not 0, but 1
    markers = markers+1
    # Now, mark the region of unknown with zero
    markers[unknown==255] = 0
    markers = cv2.watershed(img,markers)
    img[markers == -1] = [255,0,0] # boundary marked in red
    return Image.fromarray(img)

def otsu_thresholding(pil_img):
    """
    Segments the image using global (Otsu's) thresholding.
    """
    gray = np.array(pil_img.convert('L'))
    ret,thresh = cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    return Image.fromarray(thresh)

def canny_edge(pil_img, low=100, high=200):
    """
    Segments the image using Canny edge detection.
    """
    gray = np.array(pil_img.convert('L'))
    edges = cv2.Canny(gray, low, high)
    return Image.fromarray(edges)

def select_and_segment(pil_img, method, **kwargs):
    """
    Selects and applies the segmentation method.
    method: 'kmeans', 'watershed', 'otsu', 'canny'
    kwargs: parameters for each method
    """
    if method == 'kmeans':
        k = kwargs.get('k', 2)
        return kmeans_segmentation(pil_img, k=k)
    elif method == 'watershed':
        return watershed_segmentation(pil_img)
    elif method == 'otsu':
        return otsu_thresholding(pil_img)
    elif method == 'canny':
        low = kwargs.get('low', 100)
        high = kwargs.get('high', 200)
        return canny_edge(pil_img, low=low, high=high)
    else:
        raise ValueError('Unknown segmentation method')
