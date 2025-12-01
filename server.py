import asyncio
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from pathlib import Path
from loader import rotate_file_exif
from state import ServerState

IMAGE_ROOT = Path("/home/bloom/Photos")
CACHE_FILE = Path("cache.json")
IGNORED_FILE = Path("ignored.json")
LIKED_FILE = Path("liked.json")
MISSING_IMAGE = Path("missing.png")

RANDOM_SEED = 1

EXT_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

app = FastAPI()
state = ServerState()

favicon_path = Path(__file__).parent / "favicon.ico"

@app.on_event("startup")
async def startup():
    await state.load_cache(CACHE_FILE, IGNORED_FILE, LIKED_FILE)
    if not state.files:
        asyncio.create_task(state.rebuild_list_async(IMAGE_ROOT, CACHE_FILE, RANDOM_SEED))

@app.get("/favicon.ico")
async def favicon():
	return FileResponse(favicon_path, media_type="image/x-icon")

@app.get("/image/{idx}")
async def get_image(idx: int):
    if not state.files:
        return FileResponse(MISSING_IMAGE, media_type="image/png", headers={"X-Image-Index": "-1"})

    real_idx, record = state.resolve_valid_index(idx)
    await state.ensure_loaded_and_check_neighbors(real_idx)

    fpath = Path(record["path"])
    if not fpath.exists():
        raise HTTPException(404, "File missing")

    ext = fpath.suffix.lower()
    media_type = EXT_TO_MIME.get(ext, "application/octet-stream")
    return FileResponse(fpath, media_type=media_type, headers={"X-Image-Index": str(real_idx)})

@app.get("/info/{idx}")
async def get_info(idx: int):
    if not state.files:
        return {"status":"no_images"}
    real_idx, record = state.resolve_valid_index(idx)
    return record


@app.post("/ignore/{idx}")
async def ignore(idx: int):
    if not state.files:
        return {"status":"no_images"}
    real_idx, record = state.resolve_valid_index(idx)
    fname = record["path"]
    state.ignored.add(fname)
    state.save_ignore()
    return {"ignored": fname}


@app.post("/like/{idx}")
async def like(idx: int):
    if not state.files:
        return {"status":"no_images"}
    real_idx, record = state.resolve_valid_index(idx)
    fname = record["path"]
    state.liked.add(fname)
    state.save_like()
    return {"liked": fname}


@app.post("/rotate/{idx}")
async def rotate(idx: int):
    if not state.files:
        return {"status":"no_images"}
    real_idx, record = state.resolve_valid_index(idx)
    rotate_file_exif(Path(record["path"]))
    return {"rotated": record["path"]}


@app.post("/refresh")
async def refresh():
    asyncio.create_task(state.rebuild_list_async(IMAGE_ROOT, CACHE_FILE, RANDOM_SEED))
    return {"status": "refreshing"}
