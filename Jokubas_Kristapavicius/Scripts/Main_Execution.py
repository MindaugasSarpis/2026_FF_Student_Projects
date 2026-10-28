import pandas as pd
import matplotlib.pyplot as plt
import time
from Loader import image_EXIF_data_loader
from Test_02_picture_single import dominant_colour_finder
import numpy as np
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler
from sklearn.manifold import TSNE
raw_data_dir = Path(r".\Data\Raw\Test_Data")
# raw_data_dir = Path(r".\Data\Raw\Film")
start_import = time.perf_counter() 
raw_data_frame = image_EXIF_data_loader(Data_dir=raw_data_dir)
print(f"Total pictures: {len(raw_data_frame)}")
exif_data_frame = raw_data_frame.copy()
end_import = time.perf_counter()
print(f"Import meta data time elapsed: {end_import - start_import  :.3f}s")

dom_col_start = time.perf_counter()
exif_data_frame["Dominant_Colour"] = exif_data_frame["Directory"].map(
    lambda dir_path: dominant_colour_finder(dir_path, number_of_colours = 3 )
    )
dom_col_end = time.perf_counter()
print(f"Find dominant colours in all pics: {dom_col_end - dom_col_start:.3f}s")


RGB = np.array([np.array(x).flatten() for x in exif_data_frame["Dominant_Colour"]])
RGB_scaled = MinMaxScaler().fit_transform(RGB)
tsne_model = TSNE(n_components=2, perplexity=10, verbose = 1)
time_embedung = tsne_model.fit_transform(RGB_scaled)
Cameras = exif_data_frame["Make"].unique()
Color_number = np.arange(0, len(Cameras))

exif_data_frame["ColourModel"] = exif_data_frame["Make"].map(
    lambda name: float(name))
plt.scatter(time_embedung[:,0],
            time_embedung[:,1],
            c = raw_data_frame["ColourModel"]
            )
plt.axis('off')
plt.show()
# R, G, B = RGB[0], RGB[1], RGB[2] 