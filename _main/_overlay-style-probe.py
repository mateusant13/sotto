"""Renderiza a legenda NATIVA para um PNG -- o estilo, julgado a vista.

Nao abre janela: chama as MESMAS funcoes que o overlay chama (`_layout`,
`_premultiplied_bitmap`) e grava o bitmap sobre um fundo escuro, para o resultado
poder ser comparado com uma captura do player sem pôr nada no ecra do dono.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'app', 'webview'))

import clr  # noqa: E402
clr.AddReference('System.Drawing')
from System.Drawing import Bitmap, Graphics, Color, Rectangle  # noqa: E402
from System.Drawing.Imaging import ImageFormat  # noqa: E402

import overlay_paint  # noqa: E402

ROWS = sys.argv[2:] or ['maior pra ficar por último, entendeu?',
                        'Então eles estão acabando,']
OUT = sys.argv[1] if len(sys.argv) > 1 else 'overlay-style.png'
theme = overlay_paint._normalise_theme(overlay_paint._THEME_DEFAULT)
text = '\n'.join(ROWS)
lines, prev, width, height, _ = overlay_paint._layout(
    text, '', 1.0, 1920, theme)
bmp = overlay_paint._premultiplied_bitmap(lines, prev, width, height, 1.0,
                                          theme, None)
base = Bitmap(max(width, 700), height + 40)
g = Graphics.FromImage(base)
g.Clear(Color.FromArgb(60, 44, 38))
g.DrawImage(bmp, 10, 20)
os.makedirs(os.path.dirname(os.path.abspath(OUT)) or '.', exist_ok=True)
base.Save(OUT, ImageFormat.Png)
print('wrote', OUT, width, 'x', height)
