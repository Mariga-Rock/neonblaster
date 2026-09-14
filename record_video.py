#!/usr/bin/env python3
"""
Запись геймплейного видео из браузерной игры.

Требования к выходу:
  • MP4 (H.264, yuv420p — универсальная совместимость)
  • Высота <= 400 px (используем 720x400)
  • Вес <= 100 МБ (при CRF 23 обычно 2-6 МБ)
  • Длительность <= 28 сек (по умолчанию 25)
"""

import asyncio
import functools
import http.server
import os
import random
import shutil
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

from playwright.async_api import async_playwright


# ==================== НАСТРОЙКИ ====================
GAME_HTML    = Path(__file__).parent / "game.html"
OUTPUT_DIR   = Path(__file__).parent / "video_raw"
OUTPUT_MP4   = Path(__file__).parent / "kiss_blaster.mp4"

VIEWPORT_W   = 720      # 720x400 — горизонтально, высота ровно 400
VIEWPORT_H   = 400
DURATION_SEC = 25       # сколько секунд пишем геймплей
FPS          = 30
CRF          = 23       # 18 — выше качество/вес, 28 — ниже
HTTP_PORT    = 8765
# ===================================================


# ---------- Локальный HTTP-сервер (file:// иногда капризничает) ----------
def start_http_server(directory: Path, port: int):
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(directory)
    )
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


# ---------- Имитация игры: мышь, стрельба, проход апгрейдов ----------
async def simulate_input(page, duration_sec: float):
    start = time.time()
    cx, cy = VIEWPORT_W // 2, VIEWPORT_H // 2
    await page.mouse.move(cx, cy)
    await page.mouse.down()
    firing = True

    while time.time() - start < duration_sec:
        # 1) Экран апгрейдов — выбираем первую карту
        try:
            if await page.locator("#upgradeScreen").is_visible():
                if firing:
                    await page.mouse.up()
                    firing = False
                cards = page.locator(".upgrade-card")
                if await cards.count() > 0:
                    await cards.first.click()
                    await page.wait_for_timeout(250)
                continue
        except Exception:
            pass

        # 2) Game over — перезапускаем
        try:
            if await page.locator("#gameOverScreen").is_visible():
                if firing:
                    await page.mouse.up()
                    firing = False
                await page.click("#restartBtn")
                await page.wait_for_timeout(400)
                continue
        except Exception:
            pass

        # 3) Обычное движение + стрельба
        tx = random.randint(80, VIEWPORT_W - 80)
        ty = random.randint(80, VIEWPORT_H - 80)
        steps = random.randint(5, 10)
        for i in range(1, steps + 1):
            x = cx + (tx - cx) * i / steps
            y = cy + (ty - cy) * i / steps
            await page.mouse.move(x, y)
            await page.wait_for_timeout(15)
        cx, cy = tx, ty

        # 4) Иногда отпускаем ЛКМ, чтобы на видео были видны разные состояния
        if random.random() < 0.15:
            await page.mouse.up()
            firing = False
            await page.wait_for_timeout(random.randint(60, 150))
            await page.mouse.down()
            firing = True

    if firing:
        await page.mouse.up()


# ---------- Запись ----------
async def record_webm() -> Path:
    if not GAME_HTML.exists():
        sys.exit(f"❌ Нет файла: {GAME_HTML}")

    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    httpd = start_http_server(GAME_HTML.parent.resolve(), HTTP_PORT)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--autoplay-policy=no-user-gesture-required",
                "--mute-audio",
            ],
        )
        context = await browser.new_context(
            viewport={"width": VIEWPORT_W, "height": VIEWPORT_H},
            device_scale_factor=1,
            record_video_dir=str(OUTPUT_DIR.resolve()),
            record_video_size={"width": VIEWPORT_W, "height": VIEWPORT_H},
        )
        page = await context.new_page()
        await page.bring_to_front()

        url = f"http://127.0.0.1:{HTTP_PORT}/{GAME_HTML.name}"
        print(f"→ Открываю {url}")
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(1200)

        print("→ Старт игры")
        await page.click("#playBtn")
        await page.wait_for_timeout(400)

        print(f"→ Записываю {DURATION_SEC} сек геймплея...")
        await simulate_input(page, DURATION_SEC)

        # Закрываем контекст — Playwright финализирует .webm
        await context.close()
        await browser.close()

    httpd.shutdown()

    webms = sorted(OUTPUT_DIR.glob("*.webm"), key=os.path.getmtime)
    if not webms:
        sys.exit("❌ Playwright не создал .webm")
    raw = webms[-1]
    print(f"→ WebM: {raw.name}  ({raw.stat().st_size / 1024 / 1024:.1f} МБ)")
    return raw


# ---------- Конвертация в mp4 с проверкой лимитов ----------
def convert_to_mp4(raw: Path):
    if shutil.which("ffmpeg") is None:
        sys.exit("❌ ffmpeg не найден. Установи: sudo apt install ffmpeg")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(raw),
        # height → 400, ширина авто (чётная), fps=30
        "-vf", f"scale=-2:{VIEWPORT_H}:flags=lanczos,fps={FPS}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", str(CRF),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        "-t", "28",   # жёсткий кап по длительности
        str(OUTPUT_MP4),
    ]
    print("→ Конвертирую в MP4...")
    subprocess.run(cmd, check=True)

    # ---- Проверка требований ----
    size_mb = OUTPUT_MP4.stat().st_size / 1024 / 1024
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nk=1:nw=1", str(OUTPUT_MP4)
    ]).decode().strip() or 0)
    dims = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0", str(OUTPUT_MP4)
    ]).decode().strip()

    print("\n=== Результат ===")
    print(f"  Файл:         {OUTPUT_MP4}")
    print(f"  Разрешение:   {dims}")
    print(f"  Длительность: {dur:.1f} сек")
    print(f"  Вес:          {size_mb:.2f} МБ")

    ok = True
    if dur > 28:        print("  ⚠ длительность > 28 сек"); ok = False
    if size_mb > 100:   print("  ⚠ вес > 100 МБ");           ok = False
    if not dims.endswith(f",{VIEWPORT_H}"):  print(f"  ⚠ высота != {VIEWPORT_H}"); ok = False

    print("\n" + ("✅ Все требования соблюдены" if ok else "⚠ Проверь параметры выше"))


def main():
    raw = asyncio.run(record_webm())
    convert_to_mp4(raw)


if __name__ == "__main__":
    main()
