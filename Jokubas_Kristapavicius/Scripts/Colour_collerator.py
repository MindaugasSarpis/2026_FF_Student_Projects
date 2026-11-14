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
                cols LAB vector components extracted from dataframe with title 'Dominant_Colour_CIELAB'
        Function takes three (or more) dominant colours of the picture and return all possible variances
        between the colours for example: 3 dom. colours are stored in vector form [r_1,r_2,r_3], then the output
         is [distance(r_1,r_2), distance(r_1,r_3),distance(r_2,r_3)] """
    number_rows = np.shape(dom_cols)[0]
    Delta_R = np.zeros(shape=(number_rows,number_rows))
    for row in range(number_rows):
        r_row_array = np.full_like(dom_cols, fill_value=dom_cols[row])
        delta_r = r_row_array - dom_cols
        delta_r = delta_r**2
        # print(delta_r)
        
        delta_r = np.sqrt(np.sum(delta_r, axis = 1))
        Delta_R[row,:] = delta_r.T
    
    mask = np.fromfunction(lambda i,j: i>j, shape=np.shape(Delta_R))
    Pallete_Variance_values = Delta_R[mask]
    print(mask,'\n',Pallete_Variance_values)
Pallete_Variance(dom_col_test)