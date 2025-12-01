import asyncio
import json
import random
from pathlib import Path
from loader import load_cache_file, save_cache_file, scan_all_images

class ServerState:
  def __init__(self):
    self.files = []           # list of dicts { path, date, location }
    self.ignored = set()      # filenames
    self.liked = set()
    self.image_cache = {}     # idx -> bytes
    self.load_locks = {}      # idx -> asyncio.Lock
    self.load_tasks = {}      # idx -> 
    self.lock = asyncio.Lock()
    self.generation = 0

    self.cache_file = None
    self.ignored_file = None
    self.liked_file = None

# -------------------------------------------------------------

  async def load_cache(self, cache_file, ignored_file, liked_file):
    self.cache_file = cache_file
    self.ignored_file = ignored_file
    self.liked_file = liked_file

    loaded = await load_cache_file(cache_file)
    #if loaded:
    #  self.files = loaded
    self._load_list(self.ignored, ignored_file)
    self._load_list(self.liked, liked_file)

  def _load_list(self, target, path):
    if path.exists():
      try:
        d = json.loads(path.read_text())
        target.update(d)
      except:
        pass

  def save_ignore(self):
    self.ignored_file.write_text(json.dumps(list(self.ignored)))

  def save_like(self):
    self.liked_file.write_text(json.dumps(list(self.liked)))

  async def rebuild_list_async(self, folder: Path, cache_file: Path, seed):
    files = await scan_all_images(folder)
    random.seed(seed)
    random.shuffle(files)
    async with self.lock:
      self.files = files
      save_cache_file(cache_file, files)

  # -------------------------------------------------------------

  async def save_cache(self, path: Path):
    def write():
      path.write_text(json.dumps({"files": self.files}))
    await asyncio.get_running_loop().run_in_executor(None, write)

  def resolve_valid_index(self, idx: int):
    if not self.files:
      raise IndexError("Empty list")
    n = len(self.files)
    if idx < 0 or idx >= n:
      raise IndexError("out of bounds")

    start = idx
    while True:
      record = self.files[idx]
      if record["name"] not in self.ignored:
        record["index"] = idx
        return idx, record
      idx = (idx + 1) % n
      if idx == start:
        raise IndexError("All images ignored")
  # -------------------------------------------------------------

  async def _ensure_loaded(self, idx: int, wait: bool):
    if idx in self.image_cache:
      return

    lock = self.load_locks.setdefault(idx, asyncio.Lock())

    if lock.locked() and not wait:
      return

    current_gen = self.generation

    async def do_load():
      async with lock:
        if idx in self.image_cache:
          return
        if current_gen != self.generation:
          return
        try:
          path = Path(self.files[idx]["path"])
          data = await asyncio.get_running_loop().run_in_executor(None, path.read_bytes)
        except asyncio.CancelledError:
          return
        if current_gen != self.generation:
          return
        self.image_cache[idx] = data

    if wait:
      await do_load()
      return

    if idx not in self.load_tasks or self.load_tasks[idx].done():
      t = asyncio.create_task(do_load())
      self.load_tasks[idx] = t

  # -------------------------------------------------------------

  async def ensure_loaded_and_check_neighbors(self, idx: int):
    n = len(self.files)
    if n == 0:
      return

    idx = (idx + n) % n;
    await self._ensure_loaded(idx, wait=True)

    asyncio.create_task(self._ensure_loaded((idx - 1) % n, wait=False))
    asyncio.create_task(self._ensure_loaded((idx + 1) % n, wait=False))

  # -------------------------------------------------------------

  def cancel_all_loaders(self):
    for t in self.load_tasks.values():
      if not t.done():
        t.cancel()
    self.load_tasks.clear()

  # -------------------------------------------------------------

  async def refresh(self, new_files):
    async with self.lock:
      self.cancel_all_loaders()
      self.load_locks.clear()
      self.image_cache.clear()
      self.generation += 1
      self.files = new_files
