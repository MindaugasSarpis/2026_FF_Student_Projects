import pandas as pd
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist, pdist



# data = pd.read_pickle("./Data/Processed/processed_image_data.pkl")
# print(data["Dominant_Colour_CIELAB"].head())
# C_1_test = data["Dominant_Colour_CIELAB"].iloc[15] #
# C_2_test = data["Dominant_Colour_CIELAB"].iloc[20] #
"""Color distance:
    colour distance in CIELAB space between two images"""
def Delta_Colour(colour_1,colour_2, Perceptual = True):
    """Colour_1(2)- np.array of 3 or more dom colours in the picture
    The function takes colour_x as a vector filled with colour vectors that are in 
    the basiss of CIELAB, finds all possible distances between the dom colours, calculates their distances
    and then the average of those distances is the output of the function
    
    UPDATE use already built in scipy functions :(((("""
    if Perceptual:
        dist_matrix = cdist(colour_1,colour_2, metric='euclidean') 
        row_ind, col_ind = linear_sum_assignment(dist_matrix)
        avg_Delta_C = dist_matrix[row_ind,col_ind].mean()
        # number_rows = np.shape(colour_1)[0]
        # Delta_C = np.zeros(shape=(number_rows,number_rows))
        # for row in range(number_rows):
            # c_row_array = np.full_like(colour_1, fill_value=colour_1[row])
            # print(f"c2 = {colour_2}\n c_row = {c_row_array}")
            # delta_c = c_row_array - colour_2
            # print(delta_c)
            # delta_c = delta_c**2
            # print(delta_c)
            # delta_c = np.sqrt(np.sum(delta_c, axis = 1))
            # print(delta_c)
            # Delta_C[row] = delta_c
        # avg_Delta_C = np.mean(Delta_C)
        # print(Delta_C)
        # print(avg_Delta_C)
    else:
        None
    return avg_Delta_C

# Delta_Colour(C_1_test,C_1_test)


# dom_col_test = data["Dominant_Colour_CIELAB"].iloc[15] #
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
        
        delta_r = np.sqrt(np.sum(delta_r, axis = 1))
        Delta_R[row,:] = delta_r.T
    
    mask = np.fromfunction(lambda i,j: i>j, shape=np.shape(Delta_R))
    Pallete_Variance_values = np.std(Delta_R[mask])
    return Pallete_Variance_values
# Pallete_Variance(dom_col_test)