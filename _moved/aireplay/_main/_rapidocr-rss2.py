import time, json
from PIL import Image
import numpy as np
from rapidocr import RapidOCR
e = RapidOCR()
arr = np.array(Image.open(r"H:\aireplay\_main\ocr-frames\00-clean_hud.png").convert("RGB"))
for i in range(3):
    e(arr)
print("MEASURE_NOW", flush=True)
time.sleep(8)
print("DONE", flush=True)
