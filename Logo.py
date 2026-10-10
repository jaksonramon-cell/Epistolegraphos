import os
from typing import Dict
from PIL import Image


def add_logo_to_folder(
    input_folder: str,
    logo_path: str,
    overwrite: bool = False,
    output_folder: str | None = None
) -> Dict:

    # ---------------- VALIDATION ----------------

    if not os.path.isdir(input_folder):
        raise NotADirectoryError(f"Input folder not found: {input_folder}")

    if not os.path.isfile(logo_path):
        raise FileNotFoundError(f"Logo file not found: {logo_path}")

    image_files = [
        f for f in os.listdir(input_folder)
        if f.lower().endswith((".jpg", ".jpeg"))
    ]

    if not image_files:
        raise ValueError("No JPG/JPEG images found in input folder.")

    # ---------------- OUTPUT SETUP ----------------

    if not overwrite:
        if output_folder is None:
            output_folder = os.path.join(
                input_folder,
                "Fotos_con_logo"
            )

        os.makedirs(output_folder, exist_ok=True)
    else:
        output_folder = input_folder  # overwriting originals

    # ---------------- LOAD LOGO ----------------

    logo = Image.open(logo_path).convert("RGBA")

    def get_logo_size(img_width, img_height):
        if img_height > img_width:
            target_logo_width = int(img_width * 0.33)
        else:
            target_logo_width = int(img_width * 0.26)

        aspect_ratio = logo.height / logo.width
        return (
            target_logo_width,
            int(target_logo_width * aspect_ratio)
        )

    # ---------------- PROCESS IMAGES ----------------

    processed = 0
    skipped = 0

    for filename in image_files:
        try:
            img_path = os.path.join(input_folder, filename)
            img = Image.open(img_path).convert("RGBA")
            img_width, img_height = img.size

            target_logo_width, target_logo_height = get_logo_size(
                img_width,
                img_height
            )

            logo_resized = logo.resize(
                (target_logo_width, target_logo_height),
                Image.LANCZOS
            )

            padding = int(img_width * 0.01)
            position = (padding, padding)

            img.paste(logo_resized, position, logo_resized)

            output_path = os.path.join(output_folder, filename)

            img.convert("RGB").save(output_path, "JPEG")

            processed += 1

        except Exception:
            skipped += 1

    # ---------------- RETURN SUMMARY ----------------

    return {
        "processed": processed,
        "skipped": skipped,
        "total": len(image_files),
        "output_folder": output_folder
    }