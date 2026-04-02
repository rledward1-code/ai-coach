import base64
import os

# 1x1 PNG data for colored pixels in base64
PEASR_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIwAAAABJRU5ErkJggg==" # Green
LUGER_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==" # Blue
EDWARD_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQBwAEmAFA6PnUowAAAABJRU5ErkJggg==" # Red

def save_png(name, b64):
    path = os.path.join("assets", f"{name}.png")
    with open(path, "wb") as f:
        f.write(base64.b64decode(b64))
    print(f"Created {path}")

os.makedirs("assets", exist_ok=True)
save_png("luger", LUGER_PNG)
save_png("pace", PEASR_PNG)
save_png("Edward", EDWARD_PNG)
