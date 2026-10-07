import io

CSS = r'app\panel\panel.css'
c = io.open(CSS, encoding='utf-8', newline='').read()
log = []


def cut(start, end, label):
    global c
    if c.count(start) != 1:
        log.append('MISS %-40s start=%d' % (label, c.count(start)))
        return
    i = c.find(start)
    j = c.find(end, i)
    if j < 0:
        log.append('MISS %-40s end not found' % label)
        return
    j += len(end)
    while j < len(c) and c[j] in '\r\n':
        j += 1
    log.append('cut  %-40s %d bytes' % (label, j - i))
    c = c[:i] + c[j:]


# 1. the HUD's whole stylesheet block, plus the danger rules that only its
#    deleted button used.
cut('/* --------------------------------------------------------------- HUD (panel) */',
    """.reveal-button--danger:hover {
  background: rgba(248, 113, 113, 0.14);
  color: #fecaca;
}""", 'HUD css block + dead danger rules')

# 2. the hint that named the shortcut, and the `kbd` face it was the only user of.
cut('.status__hint {', """kbd {
  display: inline-block;
  min-width: 16px;
  padding: 1px 4px;
  border: 1px solid var(--line-strong);
  border-bottom-width: 2px;
  border-radius: 4px;""", 'status__hint (kbd left)')
cut('kbd {', """  border-radius: 4px;
  background: rgba(148, 163, 184, 0.12);
  font-family: inherit;
  font-size: 10px;
  line-height: 1.4;
  color: var(--text-dim);
}""", 'kbd rules')

# 3. the moved Pause button needs its own danger face, now that it is a 28 px
#    icon button in the header instead of a wide labelled button in the HUD.
c = c.replace("""  transition:
    background 120ms ease,
    color 120ms ease,
    border-color 120ms ease;
}""", """  transition:
    background 120ms ease,
    color 120ms ease,
    border-color 120ms ease;
  /* THE DRAG REGION'S ONE RULE. The header is the panel's drag handle
     (`-webkit-app-region: drag`, below), and a drag region makes its children
     undraggable AND unclickable unless they opt out — the classic defect of the
     technique. Every control opts out here, in one place, so a theme cannot
     forget it. */
  -webkit-app-region: no-drag;
  app-region: no-drag;
}

/* Pause UNLOADS the engines and costs a model load to undo. It came up here from
   the deleted HUD, where it was a wide labelled button; as a 28 px icon it keeps
   the same deliberate separation from Clear/Quit/Hide that it had there. */
.icon-button--danger {
  color: rgba(248, 180, 180, 0.9);
  border-color: rgba(248, 113, 113, 0.28);
}

.icon-button--danger:hover {
  background: rgba(248, 113, 113, 0.14);
  border-color: rgba(248, 113, 113, 0.45);
  color: #fecaca;
}""", 1)

io.open(CSS, 'w', encoding='utf-8', newline='').write(c)
for line in log:
    print(line)
left = [i + 1 for i, l in enumerate(c.split('\n')) if 'hud' in l.lower() or 'status__hint' in l]
print('remaining hud/status__hint lines:', left)
print('bytes:', len(c))
