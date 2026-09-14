#!/usr/bin/env python3
"""Генерация обложки и иконки через Cloudflare Workers AI (SDXL)."""
import os
import sys
import time
import requests
from PIL import Image

WORKER_URL = os.environ.get("CF_WORKER_URL")
API_KEY = os.environ.get("CF_IMAGE_API_KEY")

if not WORKER_URL or not API_KEY:
    print("❌ Не заданы CF_WORKER_URL и/или CF_IMAGE_API_KEY")
    sys.exit(1)
    
# ============ ПРОМПТ ОБЛОЖКИ (16:9) ============
COVER_PROMPT = (
    "Wide horizontal mobile game cover, playful kawaii "
    "anime style, arcade love-shooter. Composition for 800x470 banner: "
    "LEFT THIRD — cute cyan-blue boy hero in dynamic pose, blowing a "
    "stream of glowing heart-shaped kisses from his lips, determined "
    "smile. CENTER — curved trail of pink glowing hearts flying right "
    "with motion streaks and sparkles. RIGHT TWO-THIRDS — group of three "
    "cute chibi nurse girls in pink-and-white uniforms and nurse caps "
    "with red crosses, blonde hair, big blue eyes, rosy cheeks, "
    "cat \"ω\" mouths, surprised and charmed expressions, hearts floating "
    "above their heads. Background: dark plum-magenta gradient "
    "(#1a0510 → #3d0a24) with faint neon-pink grid, soft bokeh hearts, "
    "glowing particles. Palette: hot pink #ff2e7e, soft pink #ff8fc0, "
    "gold #ffd166, cyan #4cd4ff. BOTTOM-LEFT safe area for logo. Clean "
    "vector-inspired illustration, thick outlines, high contrast, soft "
    "rim light. No text."
)

# ============ ПРОМПТ ИКОНКИ (1:1, короткий) ============
ICON_PROMPT = (
    "Kawaii chibi nurse girl face, blonde hair, white nurse cap with pink "
    "cross, big blue eyes, rosy blush, surprised. A glowing pink heart kiss "
    "on her cheek, small heart particles around. Hot pink to dark plum "
    "gradient background. Thick outlines, flat vibrant colors, chunky vector "
    "style, mobile game icon. No text, no logos."
)


def generate_image(prompt: str, width: int, height: int, out_path: str) -> bool:
    payload = {"prompt": prompt, "width": width, "height": height}
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"→ Генерация {out_path} ({width}x{height})...")
    last_err = None
    for attempt in range(1, 4):
        try:
            resp = requests.post(WORKER_URL, json=payload, headers=headers, timeout=300)
            resp.raise_for_status()
            break
        except requests.exceptions.HTTPError as e:
            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
            print(f"  ⚠️  Попытка {attempt}/3 — {last_err}")
        except Exception as e:
            last_err = str(e)
            print(f"  ⚠️  Попытка {attempt}/3 — {last_err}")
        time.sleep(3)
    else:
        print(f"  ❌ Не удалось после 3 попыток")
        return False

    if len(resp.content) < 1000:
        print(f"  ❌ Слишком маленький ответ ({len(resp.content)} байт)")
        print(f"  Ответ: {resp.content[:300]}")
        return False

    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"  ✅ Сохранено: {out_path} ({len(resp.content)} байт)")
    return True


def make_cover():
    raw = "cover_raw1.jpg"
    if not generate_image(COVER_PROMPT, 1344, 768, raw):
        return False
    img = Image.open(raw).convert("RGB")
    img = img.resize((800, 470), Image.LANCZOS)
    img.save("cover_800x470.png", "PNG", optimize=True)
    print("  ✅ Обложка: cover_800x470.png")
    return True


def make_icon():
    raw = "icon_raw1.jpg"
    if not generate_image(ICON_PROMPT, 1024, 1024, raw):
        return False
    Image.open(raw).convert("RGB").resize(
        (512, 512), Image.LANCZOS
    ).save("icon_5122.png", "PNG", optimize=True)
    print("  ✅ Иконка: icon_5122.png")
    return True


if __name__ == "__main__":
    print("=== Генерация ассетов ===\n")
    ok1 = make_cover()
    ok2 = make_icon()
    print("\n🎉 Все ассеты готовы!" if (ok1 and ok2)
          else "\n⚠️  Часть ассетов не сгенерирована.")
    sys.exit(0 if (ok1 and ok2) else 1)
