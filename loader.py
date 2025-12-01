import asyncio
import json
import os
from pathlib import Path
from PIL import Image, ExifTags

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}

async def load_cache_file(cache_file: Path):
    loop = asyncio.get_running_loop()
    if not cache_file.exists():
        return None
    try:
        data = await loop.run_in_executor(None, cache_file.read_text)
        return json.loads(data)
    except:
        return None

def save_cache_file(cache_file: Path, records):
    cache_file.write_text(json.dumps(records))

async def scan_all_images(root: Path):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _scan_sync(root))

def _scan_sync(root: Path):
    out = []

    if not os.access(root, os.R_OK):
        print(f"No read access to {root}")
        return out

    for p in root.rglob("*"):
        if p.suffix.lower() in IMAGE_EXT:
            out.append({
                "path": str(p.resolve()),
                "name": p.name,
                "folder": p.parent.name,
                "file_date": p.stat().st_mtime,

                # Meta
                "taken_date": "",
                "location": "",
                "place": "",
            })
    if not out:
        print(f"No files found in {root.resolve()}. Maybe it's empty?")

    print(f"Found {len(out)} files in {root.resolve()}")
    return out

def rotate_file_real(path: Path):
    img = Image.open(path)
    rotated = img.rotate(-90, expand=True)
    rotated.save(path)

def rotate_file_exif(path: Path):
    img = Image.open(path)

    exif = img.getexif()

    # Orientation tag ID
    ORIENT = 274

    # Read existing orientation (default 1)
    orientation = exif.get(ORIENT, 1)

    # Map: orientation → orientation after 90° CW rotate
    rotate_map = {
        1: 6,   # normal → rotated 90 CW
        6: 3,   # 90 CW → 180
        3: 8,   # 180 → 270 CW
        8: 1,   # 270 CW → normal
    }

    new_orientation = rotate_map.get(orientation, 6)
    exif[ORIENT] = new_orientation

    img.save(path, exif=exif.tobytes())
    img.close()
