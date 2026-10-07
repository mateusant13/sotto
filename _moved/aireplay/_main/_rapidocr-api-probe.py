import numpy as np
from PIL import Image, ImageDraw, ImageFont
from rapidocr import RapidOCR
im = Image.new("RGB",(900,200),(30,40,70))
d=ImageDraw.Draw(im)
f=ImageFont.truetype("arialbd.ttf",36)
d.text((20,20),"HP 87/100  AMMO 24/90",font=f,fill=(255,255,255))
d.text((20,90),"ELE TA DE AWP",font=f,fill=(255,255,255))
arr=np.array(im)
e=RapidOCR()
out=e(arr)
print("TYPE",type(out))
print("DIR",[a for a in dir(out) if not a.startswith('_')])
print(repr(out)[:800])
