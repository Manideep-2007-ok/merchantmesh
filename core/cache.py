import hashlib
import json
from pathlib import Path

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _get_hash(caption: str, image_bytes: bytes = None) -> str:
    h = hashlib.sha256()
    h.update(caption.encode('utf-8'))
    if image_bytes:
        h.update(image_bytes)
    return h.hexdigest()

def get_cached_parse(caption: str, image_bytes: bytes = None):
    h = _get_hash(caption, image_bytes)
    cache_file = CACHE_DIR / f"{h}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                return json.load(f)
        except:
            pass
    return None

def set_cached_parse(caption: str, image_bytes: bytes, data: dict):
    h = _get_hash(caption, image_bytes)
    cache_file = CACHE_DIR / f"{h}.json"
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2)
