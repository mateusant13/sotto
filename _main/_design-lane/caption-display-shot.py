#!/usr/bin/env python3
"""caption-display-shot.py -- THE COLOUR OF THE CAPTION, over a video-ish grey.

WHY THIS EXISTS. The oracle (`caption-display-oracle.py`) measures the GEOMETRY
and the computed styles of the caption document in a real Blink. It cannot
answer "does the caption LOOK like YouTube's display", because a computed
style is not a picture: `-webkit-text-stroke: 6px` with `paint-order: stroke
fill` is a claim, and only the pixels say whether the letter kept its shape or
whether the black ate it.

SO THIS SHOOTS THE PAGE. A PNG is COLOUR TRUTH, not geometry (AGENTS.md rule
4): the frame it paints is the frame Edge gives it, and the caption's position
inside that frame is NOT a measurement of where the caption sits on the
owner's screen. For that, the oracle.

THE BACKGROUND IS GREY, NOT WHITE, ON PURPOSE. The caption window is
TRANSPARENT (the oracle proves it: `html` and `body` are
`rgba(0, 0, 0, 0)` and nothing paints behind the words), so a transparent PNG
opened in a viewer shows the glyphs against whatever the viewer uses -- and a
white viewer hides the white text. Compositing the SAME pixels over a
mid-grey is what a video looks like behind a caption, and it is the only way
to see a black OUTLINE at all.

    py -3 _main\\_design-lane\\caption-display-shot.py
    py -3 _main\\_design-lane\\caption-display-shot.py --cue=long
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

os.environ.setdefault('TMPDIR', 'I:/cc-tmp')
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import shot  # noqa: E402

PANEL = os.path.join(REPO, 'app', 'panel')
OUT = 'I:/cc-tmp/cap'

CUES = {
    'short': 'Uma vez que voce foi.',
    'two': 'e o que eu quero e que a legenda apareca aqui em baixo, igual o youtube faz',
    'long': ('esta e uma legenda muito mais comprida do que duas linhas, com '
             'palavras suficientes para ocupar tres ou quatro linhas inteiras '
             'no ecra, e o que o dono ve e sempre o fim dela, porque as '
             'palavras mais novas sao as que ele acabou de ouvir'),
}

FIXTURE = """
<script>
window.addEventListener('load', function () {
  var S = window.SottoCaption;
  if (!S) { document.title = 'NO-API'; return; }
  /* THE FACE FIRST. The `load` event does not wait for the webfont, and
     `font-display: swap` paints the caption in the FALLBACK face until it
     arrives: a shot taken at that moment is a picture of Segoe UI, not of
     the caption the owner sees. The screenshot itself is taken at the end of
     the virtual-time budget, so waiting here really does put Inter on the
     page before the pixels are taken. */
  var go = function () {
    S.set(%s, 'a linha anterior fica aqui em cima, mais fraca');
    S.listening(true);
    /* SHOT ONLY: the page was hidden until the face was in, so the picture
       cannot be a first-paint of the fallback. Nothing in the product is
       changed by this -- it is the copy in the scratch dir. */
    document.documentElement.style.visibility = '';
  };
  document.documentElement.style.visibility = 'hidden';
  if (document.fonts && document.fonts.ready) { document.fonts.ready.then(go); }
  else { go(); }
});
</script>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cue', default='two', choices=sorted(CUES))
    ap.add_argument('--outdir', default=OUT)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    work = tempfile.mkdtemp(prefix='capshot-', dir=args.outdir)
    for name in os.listdir(PANEL):
        src = os.path.join(PANEL, name)
        dst = os.path.join(work, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copyfile(src, dst)

    hp = os.path.join(work, 'caption.html')
    with open(hp, encoding='utf-8') as fh:
        html = fh.read()
    html = html.replace('</body>', (FIXTURE % json.dumps(CUES[args.cue])) + '</body>')
    # THE SHOT IS TAKEN AT THE FIRST PAINT, not at the end of the virtual-time
    # budget (MEASURED: the picture is byte-identical whether the fixture
    # waits for the font or not). `font-display: swap` therefore paints the
    # caption in the FALLBACK face. For THIS copy only, Inter is declared
    # with `font-display: block`, so the first paint is the real face.
    # (The shipped fonts.css is not touched.)
    html = html.replace('</head>',
                        '<style>@font-face{font-family:"Inter";font-style:normal;'
                        'font-weight:500;font-display:block;'
                        'src:url(../fonts/inter-latin-500-normal.woff2) format("woff2");}'
                        '</style></head>')
    with open(hp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(html)

    raw = os.path.join(args.outdir, 'caption-display-%s.png' % args.cue)
    ok, rc, err = shot.shoot(hp, raw, 900, 170, 'strip')
    print('shot ok=%s rc=%s bytes=%s' % (ok, rc, os.path.getsize(raw) if ok else -1))
    if err:
        print('stderr: ' + err[:200])
    if not ok:
        return 2

    # THE COMPOSITE: the same pixels over a mid-grey, which is what a video
    # looks like behind a caption.
    try:
        from PIL import Image
        im = Image.open(raw).convert('RGBA')
        bg = Image.new('RGBA', im.size, (0x6A, 0x7F, 0x8C, 255))
        flat = Image.alpha_composite(bg, im).convert('RGB')
        out = os.path.join(args.outdir, 'caption-display-%s-grey.png' % args.cue)
        flat.save(out)
        alpha = im.getchannel('A')
        painted = sum(1 for v in alpha.getdata() if v > 0)
        print('png %dx%d  painted(alpha>0)=%d px  composite=%s'
              % (im.size[0], im.size[1], painted, out))
    except Exception as exc:
        print('composite falhou: %r' % (exc,))
    shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
