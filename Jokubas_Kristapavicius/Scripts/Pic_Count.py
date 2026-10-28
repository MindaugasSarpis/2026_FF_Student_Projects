from pathlib import Path
formats = tuple((".jpg", "jpeg", ".tiff", ".tif", ".png"))

number_of_pics = 0
data_dir = Path(r".\Data\Raw\Film")
for root, dirs, files in Path.walk(data_dir):
    number_of_pics =number_of_pics+  len(files)
    
print(number_of_pics)