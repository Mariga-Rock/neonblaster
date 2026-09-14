
import io
import os
import requests
from PIL import Image
from github import Github, Auth

# ====== НАСТРОЙКИ ======
import sys
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not GITHUB_TOKEN:
    sys.exit("Не задан GITHUB_TOKEN: export GITHUB_TOKEN=... или передай аргументом")
REPO_NAME    = "Mariga-Rock/neonblaster"        # напр. "ivanov/my-project"
SOURCE_PATH  = "cover_1792x1024.png"       # путь к исходнику в репо
TARGET_PATH  = "cover_800x470.png"  # путь, куда сохранить (можно тот же)
TARGET_SIZE  = (800, 470)
BRANCH       = "main"                      
COMMIT_MSG   = "Resize image to 800x470"
# ========================

# 1. Авторизация
auth = Auth.Token(GITHUB_TOKEN)
g = Github(auth=auth)
repo = g.get_repo(REPO_NAME)

# 2. Получаем исходный файл
file = repo.get_contents(SOURCE_PATH, ref=BRANCH)
raw_url = file.download_url

# Если репо приватный — берём через API
if not raw_url or "raw.githubusercontent" not in raw_url:
    blob = repo.get_git_blob(file.sha)
    import base64
    raw_bytes = base64.b64decode(blob.content)
else:
    raw_bytes = requests.get(raw_url).content

# 3. Открываем и ресайзим
img = Image.open(io.BytesIO(raw_bytes))
print(f"Оригинал: {img.size}")

# Ресайз с сохранением пропорций + паддинг под 800x470
img.thumbnail(TARGET_SIZE, Image.LANCZOS)
canvas = Image.new("RGBA", TARGET_SIZE, (255, 255, 255, 0))
offset = ((TARGET_SIZE[0] - img.size[0]) // 2,
          (TARGET_SIZE[1] - img.size[1]) // 2)
canvas.paste(img, offset, img if img.mode == "RGBA" else None)

# Если хочешь просто растянуть — раскомментируй строку ниже и убери блок выше:
# canvas = img.convert("RGBA").resize(TARGET_SIZE, Image.LANCZOS)

# 4. Сохраняем в байты
buf = io.BytesIO()
out_format = "PNG" if TARGET_PATH.lower().endswith(".png") else "JPEG"
if out_format == "JPEG":
    canvas = canvas.convert("RGB")
canvas.save(buf, format=out_format, quality=95, optimize=True)
new_bytes = buf.getvalue()
print(f"Готово: {TARGET_SIZE}, {len(new_bytes)} байт")

# 5. Пробуем найти существующий файл (для update)
try:
    existing = repo.get_contents(TARGET_PATH, ref=BRANCH)
    repo.update_file(
        path=TARGET_PATH,
        message=COMMIT_MSG,
        content=new_bytes,
        sha=existing.sha,
        branch=BRANCH,
    )
    print(f"✅ Обновлён: {TARGET_PATH}")
except Exception:
    repo.create_file(
        path=TARGET_PATH,
        message=COMMIT_MSG,
        content=new_bytes,
        branch=BRANCH,
    )
    print(f"✅ Создан: {TARGET_PATH}")
