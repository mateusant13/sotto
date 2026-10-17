import sys, json
from PIL import Image
path = sys.argv[1]; outp = sys.argv[2]
im = Image.open(path).convert('RGB'); w,h = im.size
out = {'size':[w,h]}
out['row0'] = [im.getpixel((x,0)) for x in (0,1,2,3,4,w//2,w-5,w-4,w-3,w-2,w-1)]
out['col0'] = [im.getpixel((0,y)) for y in (0,1,2,3,4,h//2,h-5,h-4,h-3,h-2,h-1)]
out['lastrow'] = [im.getpixel((x,h-1)) for x in (0,1,2,3,w//2,w-4,w-3,w-2,w-1)]
out['lastcol'] = [im.getpixel((w-1,y)) for y in (0,1,2,3,h//2,h-4,h-3,h-2,h-1)]
out['centre'] = im.getpixel((w//2,h//2))
white=0; ring=0
for y in range(h):
    for x in range(w):
        if x<4 or y<4 or x>=w-4 or y>=h-4:
            ring+=1; r,g,b=im.getpixel((x,y))
            if r>200 and g>200 and b>200: white+=1
out['ring_px']=ring; out['ring_white_px']=white; out['ring_white_pct']=round(100.0*white/max(1,ring),3)
out['corners']=[im.getpixel(p) for p in ((0,0),(1,1),(2,2),(3,3),(w-1,0),(w-1,h-1),(0,h-1),(w-2,1),(1,h-2))]
open(outp,'w',encoding='utf-8').write(json.dumps(out,indent=1))
