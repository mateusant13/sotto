import json, time, statistics
import numpy as np
from PIL import Image
from rapidocr import RapidOCR
png = Image.open(r"H:\aireplay\_main\ocr-frames\00-clean_hud.png").convert("RGB")
arr = np.array(png)
e = RapidOCR()
lat=[]
for i in range(3):
    t=time.perf_counter(); e(arr); lat.append(round(time.perf_counter()-t,3))
    time.sleep(1)
print("FULL1080P", lat, "min", min(lat), "med", round(statistics.median(lat),3))

# recognizer only: hand the recognizer one already-cropped text line
line = np.array(png.crop((470, 745, 1460, 825)))
lat2=[]
for i in range(5):
    t=time.perf_counter(); e.text_rec(line); lat2.append(round(time.perf_counter()-t,4))
print("REC_LINE", lat2, "min", min(lat2))
print("LINECROP_SHAPE", list(line.shape))

lat3=[]
det = e.text_det
for i in range(3):
    t=time.perf_counter(); det(arr); lat3.append(round(time.perf_counter()-t,3))
print("DET_ONLY_FULL", lat3, "min", min(lat3))
