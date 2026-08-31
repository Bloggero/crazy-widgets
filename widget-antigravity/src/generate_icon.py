"""
Generates and applies Sword Art Online (SAO) themed high-resolution icons (PNG & ICO).
Supports multiple premium 3D HUD styles with 16x16 to 256x256 multi-layer Windows icons.
"""
import os
import sys
from PIL import Image

def apply_icon_from_file(source_image_path: str, output_dirs=None):
    if output_dirs is None:
        base = os.path.dirname(os.path.abspath(__file__))
        output_dirs = [
            os.path.join(base, "resources"),
            os.path.join(os.path.dirname(base), "resources"),
        ]

    img = Image.open(source_image_path).convert("RGBA")
    for out_dir in output_dirs:
        os.makedirs(out_dir, exist_ok=True)
        png_path = os.path.join(out_dir, "icon.png")
        img.save(png_path, format="PNG")
        ico_path = os.path.join(out_dir, "icon.ico")
        img.save(
            ico_path,
            format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        )
        print(f"Applied icon from {source_image_path} -> {png_path} & {ico_path}")

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    resources_dir = os.path.join(base, "resources")
    
    # Check if a specific option was requested
    choice = sys.argv[1] if len(sys.argv) > 1 else "option2_energy_core"
    source = os.path.join(resources_dir, f"{choice}.png")
    if os.path.exists(source):
        apply_icon_from_file(source)
    else:
        print(f"Source file {source} not found.")
