import numpy as np
from pathlib import Path, PurePath
import os
import datetime as dt
from PIL import Image, ExifTags
import pandas as pd

def image_EXIF_data_loader(Data_dir):
    """Data_dir - directory for all the files that will be analysed
        For categorization of medium parent folders of mediums must be named as following
        ["Digital", "Film", "Collage"]
        The formats supported are as following:
        [".jpg", "jpeg", ".tiff", ".tif", ".png"]"""
    formats = tuple((".jpg", "jpeg", ".tiff", ".tif", ".png"))
    mediums = ["Digital", "Film", "Collage"]
    if isinstance(Data_dir, str):
        Data_dir = Path(Data_dir) 
    Picture_directories_data = {}
    for root, dirs, files in Path.walk(Data_dir): #walks trought everything in Data_dir

        for file in files:
            if file.lower().endswith(formats):
                picture_dir = Path(root).joinpath(file)
                # Picture_directories_data[picture_dir] = "placeholder for meta data"

                empty_dic = {}
                picture = Image.open(picture_dir) #open the image sort of
                exifdata = picture.getexif()
                exif_ifd = exifdata.get_ifd(ExifTags.IFD.Exif)
                for tagid in exifdata:
                    tagname = ExifTags.TAGS.get(tagid, tagid)
                    value = exifdata.get(tagid)
                    empty_dic[f"{tagname}"] = f"{value}"
                for tagid, value in exif_ifd.items():
                    tagname = ExifTags.TAGS.get(tagid, tagid)
                    empty_dic[f"{tagname}"] = f"{value}"
                for medium in mediums:
                    if medium.lower() in (str(root)).lower():
                        empty_dic["Medium"] = medium
                empty_dic["Directory"] = picture_dir
                Picture_directories_data[picture_dir] = empty_dic
            

    df = pd.DataFrame(Picture_directories_data).T
    return df
"""Date seperator must look at all add film category pics and ASSUME that for camera Maker (column Make)
every image was taken in equally spaced time"""



# img_path_relative = Path(r"C:\Users\jkris\Desktop\University\Vilnius_University\Year_2\Sem_3\CERN Data Analysis\The_Project_Photo_Data_Exploration\Data\Raw\Test_Data\2024 09-10 Cinestill 800T\000018240018.jpg")
# img_dic = {"test": "placeholder"}
# empty_dic = {}
# im = Image.open(img_path_relative)
# exifdata = im.getexif()
# exif_ifd = exifdata.get_ifd(ExifTags.IFD.Exif)
# for tagid in exifdata:
#     tagname = ExifTags.TAGS.get(tagid, tagid)
#     value = exifdata.get(tagid)
#     empty_dic[f"{tagname:25}"] = f"{value}"
# for tagid, value in exif_ifd.items():
#     tagname = ExifTags.TAGS.get(tagid, tagid)
#     empty_dic[f"{tagname:25}"] = f"{value}"
# img_dic["test"] = empty_dic
# df = pd.DataFrame(img_dic)
# print(df)



# formats = tuple((".jpg", "jpeg", ".tiff", ".tif", ".png"))
# mediums = ["Digital", "Film", "Collage"]
# r"""
# 1 . It must load all the paths in Data\Raw and store it pandas dataframe
# 2 . It has to read the relevant the meta_data
#     For film photography it only needs the Date Taken and Camera Maker
#     For Digital Photography it must extract all the meta data
#     For Collages and scanned media Just Date Taken
# Must be located in the Scripts folder for itself to navigate to Raw Data
# Could improve upone keys
# """
# Data_dir = Path(r".\Data\Raw\Test_Data")
# Picture_directories_data = {}
# for root, dirs, files in Path.walk(Data_dir): #walks trought everything in Data_dir

#     for file in files:
#         if file.lower().endswith(formats):
#             picture_dir = Path(root).joinpath(file)
#             # Picture_directories_data[picture_dir] = "placeholder for meta data"

#             empty_dic = {}
#             picture = Image.open(picture_dir) #open the image sort of
#             exifdata = picture.getexif()
#             exif_ifd = exifdata.get_ifd(ExifTags.IFD.Exif)
#             for tagid in exifdata:
#                 tagname = ExifTags.TAGS.get(tagid, tagid)
#                 value = exifdata.get(tagid)
#                 empty_dic[f"{tagname}"] = f"{value}"
#             for tagid, value in exif_ifd.items():
#                 tagname = ExifTags.TAGS.get(tagid, tagid)
#                 empty_dic[f"{tagname}"] = f"{value}"
#             for medium in mediums:
#                 if medium.lower() in (str(root)).lower():
#                     empty_dic["Medium"] = medium

#             Picture_directories_data[picture_dir] = empty_dic
        

# df = pd.DataFrame(Picture_directories_data).T
