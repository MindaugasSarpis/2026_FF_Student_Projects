import pandas as pd
import matplotlib.pyplot as plt
import time
from Loader import image_EXIF_data_loader
from Dominant_Colour import dominant_colour_finder
import numpy as np
from pathlib import Path
import skimage
from sklearn.preprocessing import MinMaxScaler
from sklearn.manifold import TSNE
raw_data_dir = Path(r"./Data/Raw")
# raw_data_dir = Path(r".\Data\Raw\Film")
###IMPORT THE DATA
start_import = time.perf_counter() 
raw_data_frame = image_EXIF_data_loader(Data_dir=raw_data_dir)
print(f"Total pictures: {len(raw_data_frame)}")
exif_data_frame = raw_data_frame.copy()
end_import = time.perf_counter()
print(f"Import meta data time elapsed: {end_import - start_import  :.3f}s")

###FIND DOM COLOR FOR EACH PIC
dom_col_start = time.perf_counter()
exif_data_frame["Dominant_Colour"] = exif_data_frame["Directory"].map(
    lambda dir_path: dominant_colour_finder(dir_path, number_of_colours = 3 )
    )
exif_data_frame["Dominant_Colour_CIELAB"] = exif_data_frame["Dominant_Colour"].map(
    lambda dom_col_RGB: skimage.color.rgb2lab(np.array(dom_col_RGB, dtype = float)/255.0)
    if isinstance(dom_col_RGB,np.ndarray) else np.nan)
exif_data_frame = exif_data_frame.dropna(subset=["Dominant_Colour"])
dom_col_end = time.perf_counter()
print(f"Find dominant colours in all pics: {dom_col_end - dom_col_start:.3f}s")

exif_data_frame.to_pickle(r"./Data/Processed/processed_image_data.pkl")
