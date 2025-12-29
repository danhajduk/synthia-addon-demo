from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path
from datetime import datetime

router = APIRouter()

# Keep runtime inside addon folder: addons/visuals/runtime/...
ADDON_ROOT = Path(__file__).resolve().parents[1]  # .../addons/visuals
RUNTIME_ROOT = ADDON_ROOT / "runtime"
PUBLISHED_DIR = RUNTIME_ROOT / "published"
CURRENT_PATH = PUBLISHED_DIR / "current.jpg"


def ensure_dirs():
    (RUNTIME_ROOT / "weather").mkdir(parents=True, exist_ok=True)
    (RUNTIME_ROOT / "avatar").mkdir(parents=True, exist_ok=True)
    (RUNTIME_ROOT / "gen").mkdir(parents=True, exist_ok=True)
    (RUNTIME_ROOT / "meta").mkdir(parents=True, exist_ok=True)
    (RUNTIME_ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    PUBLISHED_DIR.mkdir(parents=True, exist_ok=True)


def publish_placeholder():
    # Lazy import so the addon can still mount even if Pillow isn't installed yet.
    from PIL import Image, ImageDraw

    ensure_dirs()
    img = Image.new("RGB", (1280, 720), color=(20, 20, 24))
    draw = ImageDraw.Draw(img)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    draw.text((40, 40), "Synthia Visuals Engine", fill=(230, 230, 235))
    draw.text((40, 90), "Step 0: placeholder published", fill=(180, 180, 190))
    draw.text((40, 140), f"Generated: {now}", fill=(140, 140, 150))
    img.save(CURRENT_PATH, quality=92)


@router.get("/health")
def health():
    if not CURRENT_PATH.exists():
        publish_placeholder()
    return {"status": "ok", "addon": "visuals"}


@router.get("/status")
def status():
    # Status should not *need* Pillow, but we publish once so UI/HA has an image.
    if not CURRENT_PATH.exists():
        publish_placeholder()

    return {
        "status": "ok",
        "addon": "visuals",
        "runtime_root": str(RUNTIME_ROOT),
        "current_image": str(CURRENT_PATH),
        "current_exists": CURRENT_PATH.exists(),
    }


@router.get("/current.jpg")
def current_image():
    if not CURRENT_PATH.exists():
        publish_placeholder()
    return FileResponse(str(CURRENT_PATH), media_type="image/jpeg")


@router.post("/publish/placeholder")
def force_placeholder():
    publish_placeholder()
    return JSONResponse({"ok": True, "path": str(CURRENT_PATH)})


class BackendAddon:
    """
    Minimal object to satisfy the core loader.

    It only needs:
      - id: str
      - name: str
      - router: APIRouter
    """
    def __init__(self, id: str, name: str, router: APIRouter) -> None:
        self.id = id
        self.name = name
        self.router = router


addon = BackendAddon(
    id="demo",
    name="Demo Addon",
    router=router,
)
