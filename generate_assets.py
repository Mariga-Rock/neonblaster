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
    "Mobile game cover art, wide 16:9 composition. A cute kawaii chibi "
    "nurse girl face, blonde hair, white nurse cap with a pink cross, "
    "big sparkling blue eyes, rosy blush, omega-shaped mouth, slightly "
    "blushing and surprised. She is being hit by a big glowing pink heart "
    "kiss that covers part of her cheek, small heart particles bursting "
    "around. Background: bold radial gradient from hot pink to dark plum, "
    "subtle glow. Thick black outlines, flat vibrant colors, glossy "
    "highlights, drop shadow. Chunky vector style, polished mobile game "
    "art, centered composition, high contrast. Empty clean space at the "
    "top for a title. No text, no letters, no numbers, no logos, "
    "no watermarks."
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
    raw = "cover_raw.jpg"
    if not generate_image(COVER_PROMPT, 1344, 768, raw):
        return False
    img = Image.open(raw).convert("RGB")
    img = img.resize((1792, 1024), Image.LANCZOS)
    img.save("cover_1792x1024.png", "PNG", optimize=True)
    print("  ✅ Обложка: cover_1792x1024.png")
    return True


def make_icon():
    raw = "icon_raw.jpg"
    if not generate_image(ICON_PROMPT, 1024, 1024, raw):
        return False
    Image.open(raw).convert("RGB").resize(
        (512, 512), Image.LANCZOS
    ).save("icon_512.png", "PNG", optimize=True)
    print("  ✅ Иконка: icon_512.png")
    return True


if __name__ == "__main__":
    print("=== Генерация ассетов ===\n")
    ok1 = make_cover()
    ok2 = make_icon()
    print("\n🎉 Все ассеты готовы!" if (ok1 and ok2)
          else "\n⚠️  Часть ассетов не сгенерирована.")
    sys.exit(0 if (ok1 and ok2) else 1)
