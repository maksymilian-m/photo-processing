from pathlib import Path
from PIL import Image
import pillow_heif

def get_exif_date(image):
    """Wyciąga datę wykonania zdjęcia z metadanych EXIF."""
    try:
        exif = image.getexif()
        if exif:
            # 36867 to standardowy kod dla DateTimeOriginal
            # 306 to DateTime (data modyfikacji/zapisu)
            for tag_id in [36867, 306]:
                date_str = exif.get(tag_id)
                if date_str:
                    # Format EXIF to zazwyczaj "YYYY:MM:DD HH:MM:SS"
                    # Zamieniamy na bezpieczny format nazwy pliku
                    return date_str.replace(":", "-").replace(" ", "_")
    except Exception:
        pass
    return None

def process_photos(source_dir, target_dir, quality=95):
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    
    pillow_heif.register_heif_opener()
    
    # Obsługujemy HEIC oraz opcjonalnie JPG, jeśli już jakieś są w folderze
    extensions = ['.heic', '.heif', '.jpg', '.jpeg', '.png']
    files = [f for f in Path(source_dir).iterdir() if f.suffix.lower() in extensions]
    
    print(f"Rozpoczynam przetwarzanie {len(files)} plików...")

    for file_path in files:
        try:
            with Image.open(file_path) as img:
                # Pobranie daty i EXIF
                photo_date = get_exif_date(img)
                exif_data = img.info.get("exif")
                
                # Ustalenie bazowej nazwy
                if photo_date:
                    new_name_base = photo_date
                else:
                    new_name_base = f"BRAK-DATY_{file_path.stem}"
                
                # Obsługa kolizji nazw (kilka zdjęć w tej samej sekundzie)
                counter = 1
                final_name = f"{new_name_base}.jpg"
                while (target_path / final_name).exists():
                    final_name = f"{new_name_base}_{counter}.jpg"
                    counter += 1
                
                target_file = target_path / final_name
                
                # Konwersja i zapis
                # Konwertujemy do RGB (ważne przy HEIC/PNG -> JPG)
                rgb_img = img.convert("RGB")
                
                save_params = {"quality": quality, "optimize": True}
                if exif_data:
                    save_params["exif"] = exif_data
                
                rgb_img.save(target_file, "JPEG", **save_params)
                print(f"Przetworzono: {file_path.name} -> {final_name}")
                
        except Exception as e:
            print(f"Błąd przy pliku {file_path.name}: {str(e)}")

# Uruchomienie
process_photos('zdjecia_z_chmury', 'zdjecia_do_albumu')