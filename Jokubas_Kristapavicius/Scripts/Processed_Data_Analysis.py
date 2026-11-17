import pandas as pd
from Colour_collerator import Pallete_Variance, Delta_Colour
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

data = pd.read_pickle("./Data/Processed/processed_image_data.pkl")
data = data[data.index.notna()].dropna(subset=["Dominant_Colour_CIELAB"])
data["Pallete_Spread"] = data["Dominant_Colour_CIELAB"].apply(Pallete_Variance)
#fixin collage stuff
collage_mask = data["Medium"] == "Collage"
data.loc[collage_mask, "DateTimeOriginal"] = data.loc[collage_mask, "DateTimeDigitized"]

data["Date"] = pd.to_datetime(
    data["DateTimeOriginal"].astype(str).str.strip(),
    format="%Y:%m:%d %H:%M:%S",
    errors="coerce"
)

#seperate datframes by medium
data_film = data[data["Medium"] == "Film"].sort_values('Date').copy()
data_Collage = data[data["Medium"] == "Collage"].dropna(subset=["Date"]).sort_values('Date').copy()
data_Digital = data[data["Medium"] == "Digital"].sort_values('Date').copy()

collage_vs_film = pd.merge_asof(data_Collage, data_film, on='Date', direction='backward',suffixes=('_collage', '_film'))
collage_vs_film['Delta_Colour'] = collage_vs_film.apply( lambda row: Delta_Colour(row['Dominant_Colour_CIELAB_collage'],row['Dominant_Colour_CIELAB_film']), axis = 1)

