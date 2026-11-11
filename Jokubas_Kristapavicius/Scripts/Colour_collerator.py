import pandas as pd
import numpy as np
"""Must do the fol"""


data = pd.read_pickle("./Data/Processed/processed_image_data.pkl")
# print(data["Dominant_Colour_CIELAB"].head())
"""Color distance:
    colour distance in CIELAB space between two images"""
def Delta_Colour(colour1,colour2):
    return None

dom_col_test = data["Dominant_Colour_CIELAB"].iloc[15] #
"""Pallete variance:
    image wise how spread is the pallete"""
def Pallete_Variance(dom_cols):
    """dom_cols - np.array of dominant colours in the list
                in CIELAB format row - different colour
                cols LAB vector components"""
    # print(dom_cols)
    # dom_cols = np.array()
    # dom_cols = pd.DataFrame()
    # dom_cols.to_numpy()
    number_rows = np.shape(dom_cols)[0]
    Delta_R = np.zeros(shape=(number_rows,number_rows))
    for row in range(number_rows):
        r_row_array = np.full_like(dom_cols, fill_value=dom_cols[row])
        delta_r = r_row_array - dom_cols
        delta_r = delta_r**2
        # print(delta_r)
        
        delta_r = np.sqrt(np.sum(delta_r, axis = 1))
        print(delta_r.T)
        # Delta_R[]
        
    # print(r_1_array)
Pallete_Variance(dom_col_test)