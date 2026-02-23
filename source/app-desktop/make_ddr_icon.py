import os
import sys

try:
    from PIL import Image
except Exception as exc:
    print(f"[DDR] Icon step skipped: Pillow unavailable ({exc})")
    sys.exit(0)


def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    png_path = os.path.join(root_dir, "source", "app-web", "ddr.png")
    ico_path = os.path.join(root_dir, "source", "app-desktop", "ddr.ico")

    if not os.path.exists(png_path):
        print(f"[DDR] Icon step skipped: source PNG not found at {png_path}")
        return

    img = Image.open(png_path).convert("RGBA")
    img.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"[DDR] Generated icon: {ico_path}")


if __name__ == "__main__":
    main()
