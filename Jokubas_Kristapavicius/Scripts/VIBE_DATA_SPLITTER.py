import os
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, timedelta
import piexif
from PIL import Image, ExifTags

class FilmExifApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Film EXIF Injector")
        self.root.geometry("450x420")
        self.folder_path = tk.StringVar()
        
        # UI Elements
        tk.Button(root, text="Select Folder", command=self.select_folder).pack(pady=10)
        tk.Label(root, textvariable=self.folder_path, fg="blue").pack(pady=5)
        
        tk.Label(root, text="Load Date (YYYY-MM-DD):").pack()
        self.start_entry = tk.Entry(root, width=25)
        self.start_entry.pack(pady=5)
        
        tk.Label(root, text="Unload Date (YYYY-MM-DD):").pack()
        self.end_entry = tk.Entry(root, width=25)
        self.end_entry.pack(pady=5)
        
        tk.Label(root, text="Film Used (Optional):").pack()
        self.model_entry = tk.Entry(root, width=25)
        self.model_entry.pack(pady=5)

        tk.Label(root, text="ISO (Optional):").pack()
        self.iso_entry = tk.Entry(root, width=25)
        self.iso_entry.pack(pady=5)
        
        tk.Button(root, text="Start Processing", command=self.process_images, bg="green", fg="white").pack(pady=20)
        
        self.status_label = tk.Label(root, text="")
        self.status_label.pack()

    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path.set(folder)

    def process_images(self):
        folder = self.folder_path.get()
        start_str = self.start_entry.get().strip()
        end_str = self.end_entry.get().strip()
        film_model = self.model_entry.get().strip()
        iso_str = self.iso_entry.get().strip()
        
        if not folder or not start_str or not end_str:
            messagebox.showerror("Error", "Folder and both dates are required.")
            return

        try:
            start_date = datetime.strptime(start_str, "%Y-%m-%d")
            end_date = datetime.strptime(end_str, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Use exactly YYYY-MM-DD")
            return

        if end_date <= start_date:
            messagebox.showerror("Error", "Unload date must be after Load date.")
            return

        # Validate ISO if provided
        iso_val = None
        if iso_str:
            try:
                iso_val = int(iso_str)
            except ValueError:
                messagebox.showerror("Error", "ISO must be a valid number.")
                return

        valid_extensions = ('.png', '.jpeg', '.jpg', '.tiff', '.tif')
        images = [f for f in os.listdir(folder) if f.lower().endswith(valid_extensions)]
        
        images.sort()
        
        if not images:
            messagebox.showerror("Error", "No valid images found in the selected folder.")
            return

        num_images = len(images)
        
        if num_images > 1:
            interval = (end_date - start_date) / (num_images - 1)
        else:
            interval = timedelta(0)

        success_count = 0
        
        for i, img_name in enumerate(images):
            img_path = os.path.join(folder, img_name)
            current_time = start_date + (interval * i)
            exif_time_str = current_time.strftime("%Y:%m:%d %H:%M:%S")
            
            ext = img_name.lower()
            try:
                if ext in ('.jpg', '.jpeg'):
                    self.process_jpeg(img_path, exif_time_str, film_model, iso_val)
                else:
                    self.process_lossless(img_path, exif_time_str, film_model, iso_val)
                success_count += 1
            except Exception as e:
                print(f"Failed to process {img_name}: {e}")

        self.status_label.config(text=f"Success! Updated {success_count}/{num_images} images.", fg="green")
        messagebox.showinfo("Done", f"Successfully updated {success_count} images.")

    def process_jpeg(self, filepath, time_str, model, iso):
        try:
            exif_dict = piexif.load(filepath)
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

        exif_dict["0th"][piexif.ImageIFD.DateTime] = time_str.encode("utf-8")
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = time_str.encode("utf-8")
        exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = time_str.encode("utf-8")
        
        if model:
            exif_dict["0th"][piexif.ImageIFD.Model] = model.encode("utf-8")
            
        # ISO Speed Ratings Tag in ExifIFD expects an integer
        if iso is not None:
            exif_dict["Exif"][piexif.ExifIFD.ISOSpeedRatings] = iso
        
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, filepath)

    def process_lossless(self, filepath, time_str, model, iso):
        with Image.open(filepath) as img:
            exif = img.getexif()
            
            exif[306] = time_str 
            
            if model:
                exif[272] = model    
            
            exif_ifd = exif.get_ifd(0x8769)
            exif_ifd[36867] = time_str 
            exif_ifd[36868] = time_str 
            
            # ISO Speed Ratings tag is 34855
            if iso is not None:
                exif_ifd[34855] = iso
            
            img.save(filepath, exif=exif)

if __name__ == "__main__":
    root = tk.Tk()
    app = FilmExifApp(root)
    root.mainloop()