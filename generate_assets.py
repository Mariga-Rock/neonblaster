#!/usr/bin/env python3
"""Генерация обложки и иконки через Cloudflare Workers AI (flux-1-schnell)."""
import os
import sys
import requests
from PIL import Image

WORKER_URL = os.environ.get("CF_WORKER_URL")
API_KEY = os.environ.get("CF_IMAGE_API_KEY")

if not WORKER_URL or not API_KEY:
    print("❌ Не заданы CF_WORKER_URL и/или CF_IMAGE_API_KEY")
    sys.exit(1)

COVER_PROMPT = (
    "Promotional cover art for a minimalist 2D top-down arena shooter game "
    "Neon Arena. Glowing cyan circle hero in the center firing bright yellow "
    "projectiles. Red squares and orange triangle enemies approach from edges. "
    "Dark navy background with subtle neon grid, soft vignette. Explosions, "
    "neon particles, speed lines. Flat vector illustration, high contrast, "
    "vibrant neon colors. Clean empty band at the top third for the game title. "
    "No text, no letters, no numbers, no logos, no watermarks."
)

ICON_PROMPT = (
    "Mobile game icon for a minimalist 2D top-down shooter Neon Arena. "
    "Centered glowing cyan circle hero with a small dark gun barrel pointing "
    "upper-right. A red square enemy lower-left, an orange triangle lower-right, "
    "both with soft neon outlines. Deep dark navy background with subtle neon "
    "grid and radial glow behind the hero. Flat vector, bold simple shapes, "
    "thick clean outlines, high contrast, neon cyan, red and orange accents. "
    "Readable at small sizes. No text, no letters, no numbers, no logos."
)


def generate_image(prompt: str, out_path: str) -> bool:
    """Отправляет запрос к Worker'у и сохраняет изображение."""
    # ВАЖНО: передаём ТОЛЬКО prompt, без width и height
    payload = {"prompt": prompt}
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"→ Генерация {out_path}...")
    try:
        resp = requests.post(WORKER_URL, json=payload, headers=headers, timeout=300)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"  ❌ HTTP ошибка: {e}")
        print(f"  Ответ: {resp.text[:300]}")
        return False
    except Exception as e:
        print(f"  ❌ Ошибка запроса: {e}")
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
    """Обложка 16:9 → кроп/ресайз до 1792x1024."""
    raw = "cover_raw.jpg"
    if not generate_image(COVER_PROMPT, raw):
        return False

    img = Image.open(raw).convert("RGB")
    tw, th = 1792, 1024
    tr = tw / th
    w, h = img.size
    r = w / h
    if r > tr:
        new_w = int(h * tr)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / tr)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
    img = img.resize((tw, th), Image.LANCZOS)
    img.save("cover_1792x1024.png", "PNG", optimize=True)
    print("  ✅ Обложка: cover_1792x1024.png")
    return True


def make_icon():
    """Иконка 1:1 → ресайз до 512x512."""
    raw = "icon_raw.jpg"
    if not generate_image(ICON_PROMPT, raw):
        return False

    img = Image.open(raw).convert("RGB")
    img.resize((512, 512), Image.LANCZOS).save("icon_512.png", "PNG", optimize=True)
    print("  ✅ Иконка: icon_512.png")
    return True


if __name__ == "__main__":
    print("=== Генерация ассетов Neon Blaster ===\n")
    ok_cover = make_cover()
    ok_icon = make_icon()
    if ok_cover and ok_icon:
        print("\n🎉 Все ассеты готовы!")
        sys.exit(0)
    else:
        print("\n⚠️  Часть ассетов не сгенерирована.")
        sys.exit(1)
