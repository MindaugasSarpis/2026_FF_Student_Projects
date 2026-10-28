from PIL import Image
import numpy as np
import pandas as pd
from pathlib import Path
import cv2 
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from Loader import image_EXIF_data_loader as data_loader
def dominant_colour_finder(image_dir,number_of_colours = 3,max_dim = 200, seed = 67):
    """
    image_dir - directory of an image
    number_of_colours - specified number of dominant colours
    max_dim - picture will be resized such that max dimension is max_dim
    seed - well it is seed as numpy randoms and stuff

    returns the array of dominant colours in RGB space
    """
    image = cv2.imread(image_dir, cv2.COLOR_BGR2RGB)
    image = cv2.cvtColor(image,cv2.COLOR_BGR2RGB)  #translates colour to usual RGB

    height, width = image.shape[:2]
    if max(height, width) > max_dim: #resized image for efficient k clustering
        scale = max_dim / float(max(height,width))
        resize_width = int(scale * width)    
        resize_height = int(scale * height)
        image_resized = cv2.resize(image,(resize_width,resize_height), interpolation=cv2.INTER_AREA)
    pixels_image_resized = image_resized.reshape(-1,3) #flatten the image i.e. pixels are in one row, inside pixel - rgb
    
    kmeans = KMeans(n_clusters = number_of_colours, random_state = seed, n_init=10)
    kmeans.fit(pixels_image_resized)#plots each pixel in RGB space, assigns each pixel to nearest cluster, loops again until the cluster centre doesnt mmove
    dominant_colors = kmeans.cluster_centers_.astype(int)# returns those clusters as RGB coordinates
    return dominant_colors

raw_data_dir = Path(r".\Data\Raw\Test_Data")
# picture = cv2.imread(dir_picture, cv2.IMREAD_COLOR_RGB)
data_frame_pic_general_data = data_loader(raw_data_dir)

test_pic_row = data_frame_pic_general_data.iloc[50,:]
image = cv2.imread(r"C:\Users\jkris\Desktop\test.png")
# image = cv2.imread(test_pic_row["Directory"])
image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

max_dimension = 200 #px Resized for efficient k-clustering
height, width = image.shape[:2]
if max(height, width) > max_dimension:
    scale = max_dimension / float(max(height,width))
    resize_width = int(scale * width)    
    resize_height = int(scale * height)
    image_resized = cv2.resize(image,(resize_width,resize_height), interpolation=cv2.INTER_AREA)
image_copy = image.copy()
image_copy[:,:,0] = 0

image_resized_pixels = image_resized.reshape(-1,3)
print(image_resized_pixels)
kmeans = KMeans(n_clusters=3, random_state=42, n_init = 10)
kmeans.fit(image_resized_pixels)
dominant_colors = kmeans.cluster_centers_.astype(int)
print("Dominant RGB Colors:\n", dominant_colors)

palette = np.zeros((50, 300, 3), dtype=np.uint8)
block_width = 300 // 3

for i, color in enumerate(dominant_colors):
    palette[:, i * block_width : (i + 1) * block_width] = color

# Display the image_resized and the color palette side-by-side
fig, axes = plt.subplots(1, 2, figsize=(10, 5))

axes[0].imshow(image)
axes[0].set_title("Original Image")
axes[0].axis("off")

axes[1].imshow(palette)
axes[1].set_title("Top 3 Dominant Colors")
axes[1].axis("off")



plt.tight_layout()
plt.show()
# # del image, 

