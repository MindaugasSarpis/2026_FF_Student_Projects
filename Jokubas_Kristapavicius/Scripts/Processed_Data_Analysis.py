import pandas as pd
from Colour_collerator import Pallete_Variance
data = pd.read_pickle("./Data/Processed/processed_image_data.pkl")
data = data[data.index.notna()].dropna(subset=["Dominant_Colour_CIELAB"])
data["Inter_Variance"] = data['Dominant_Colour_CIELAB'].map(
    lambda colours : Pallete_Variance(colours)
)
print(data["Medium"].unique())