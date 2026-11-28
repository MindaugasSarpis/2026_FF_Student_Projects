import pandas as pd
from Colour_collerator import Pallete_Variance, Delta_Colour
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

def compare_medium(df_target, df_reference, target_suffix, ref_suffix, direction = 'backward', tolerance = pd.Timedelta('60 days')):
    """Alligns dataframes in chosen direction and and computes according to function
        direction:
            backward- selects last row in the reference dataframe whose 'on' key is less than or equel to the target df
                        i.e. picture in the target df is compared to multiple pics on the reference df such that the picture
                        in reference is taken before the picture in targer df
            nearest -  sort of creates cluster around picture in df_target where pic in df_references is at the smalles distance
                        based on data ('on')
        returns a merged data frame where Delta_Colour 
    """
    merged = pd.merge_asof(
        df_target.dropna(subset=['Date']).sort_values('Date'),
        df_reference.dropna(subset=['Date']).sort_values('Date'),
        on = 'Date',
        direction= direction,
        suffixes=(target_suffix,ref_suffix),
        tolerance=tolerance
    )
    col_a = f'Dominant_Colour_CIELAB{target_suffix}'
    col_b = f'Dominant_Colour_CIELAB{ref_suffix}'
    merged['Delta_Colour'] = [
        Delta_Colour(a,b) for a,b in zip(merged[col_a],merged[col_b])
    ]

    col_a = f'Pallete_Spread{target_suffix}'
    col_b = f'Pallete_Spread{ref_suffix}'
    merged['Delta_Pallete_Spread'] = abs(merged[col_a].values - merged[col_b].values)

    return merged
###priming the data
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

print(data.columns)
#seperate datframes by medium
data_film = data[data["Medium"] == "Film"].sort_values('Date').copy()
data_Collage = data[data["Medium"] == "Collage"].dropna(subset=["Date"]).sort_values('Date').copy()
data_Digital = data[data["Medium"] == "Digital"].sort_values('Date').copy()

###COMPARING

df_col_film = compare_medium(data_Collage, data_film, '_collage', '_film', direction='backward')
df_col_dig  = compare_medium(data_Collage, data_Digital, '_collage', '_digital', direction='backward')
df_film_dig = compare_medium(data_film, data_Digital, '_film', '_digital', direction = 'nearest')

###Ploting
fig, ax = plt.subplots()
ax.scatter(
    df_film_dig['Date'],
    df_film_dig['Delta_Pallete_Spread'],
    )
ax.grid(True, alpha = 0.5)
plt.show()