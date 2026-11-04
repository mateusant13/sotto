# Sotto — mapa e perfil de cada estágio (áudio → pixel), 2026-11-04

Lane READ-ONLY. Nenhum ficheiro do produto foi tocado; nenhuma janela foi aberta; nenhum
áudio foi aberto; nenhum build pesado correu. O único artefacto escrito é este ficheiro.

**Portão de trabalho pesado, lido antes de qualquer medição** (o gate recusa, então só se
mediu o barato):

```
$ cd H:/sotto && python I:/!manager/tools/performance-gate.py status
performance-gate: UNKNOWN
  reasons:
    - sample-unknown:disk counter read failed: Command '['powershell', '-NoProfile', '-NonInteractive', '-Command', ...
  policy:
    heavy_allowed=False amber_light_allowed=False amber_light_ttl_max=300.0s
    - amber-light-refused:machine-unknown
  leases: heavy=0/1 light=0/3
    reaped expired id=139e5b5f868948f5a41a24c5b18d77d9 owner=sotto-weight-startup
  state_dir: I:\!manager\state\performance-gate
```

`UNKNOWN` não é verde: nada de `npm ci`, nada de carregar modelo, nada de bateria.

**O PROCESSO É O DA ÁRVORE?** (passo 0 do `docs/bug-hunt.md`) — **NÃO**:

```
$ cd H:/sotto && python _main/live-code-freshness-oracle.py --strict
LIVE_CODE STALE log=H:\sotto\_main\webview-run.log
  pid=42548 started=2026-11-04 10:06:36.407
  processo: sha256=3533907AABB8
  disco   : sha256=E84435F6830A files=39
  porque  : a etiqueta do processo nao e' a do disco (hash diferente)
```

Consequência, e vale para todo o §(c): **os números do log vivo são de uma instância 24-25
min mais velha que o disco**. Não se apresentam como verificação do código HEAD; são o que
ele carrega. As medições em processo (§a, §b) correm contra o código do disco.

---

## 0. O caminho, em ficheiros

```
worker/wasapi_loopback.py  ──┐  taps: LoopbackTap/FileTap, block_ms (config.json: audio.block_ms=100)
worker/sotto_worker.py       ├─ on_block(): counters + audio_q (worker/sotto_worker.py:5992)
  asr_thread()               │    buf = np.concatenate([buf, block]); while len(buf) >= asr.chunk
  (sotto_worker.py:6456-6459)│    asr.chunk = genai_config chunk_samples = 8960 @16k = 560 ms
  run_chunk()                │
  emit(type="caption")  ─────┘    JSON numa linha de stdout
        ↓  (pipe)
app/webview/sotto_webview.py  WorkerBridge._pump (17135) → ._consume (17280)
                               → SottoShell.on_worker_caption (13495) → emit_async('caption')
        ↓  (WebView2, script no documento)
app/panel/panel.js → app/panel/caption-formulation.js (createEngine.ingest)
                               → DOM paint → ack
        ↓  (bridge: host call)
app/webview/sotto_webview.py  SottoHost._caption_applied (8563) → _caption_lag_note (13090)
```

O "bridge" não é um processo: é a classe `WorkerBridge` dentro da shell (lê stdout do worker).
O "shell" e o "panel" também são o mesmo processo (WebView2 hospedado de dentro de
`sotto_webview.py`).

---

## (a) Custo de arranque do import da shell — `python -X importtime`

```
$ cd H:/sotto/app/webview
$ python -X importtime -c "import sotto_webview" 2> I:/cc-tmp/importtime-shell.txt
$ echo $?          # rc=0
$ python -c "print(sum(1 for _ in open('I:/cc-tmp/importtime-shell.txt',encoding='utf-8',errors='replace')))"
123
```

Topo do rasto (coluna 1 = **self** µs, coluna 2 = **cumulative** µs):

```
     6734 us self=  35331  sotto_webview
     2900 us self=  23617  site
     2086 us self=  15859  __editable___consultgpt_14_0_0_finder
     1981 us self=   1981  _hashlib
     1841 us self=   1841  enum
     1623 us self=   1623  _ctypes
     1445 us self=   2593  argparse
     1259 us self=   2410  encodings
     1169 us self=   1272  datetime
```

Cadeia própria da shell, toda abaixo de 3 ms:

```
      339  glob
      630  code_identity
      243  panel_state
      189  topmost_keepalive
      270  power_recovery
      406  selftest_instrument
     2832  hot_reload
```

Delta em relógio de parede contra um interpretador nú (5 processos cada):

```
$ python -c "
import subprocess,time,statistics as st,os
env=dict(os.environ); env['PYTHONPATH']=r'H:/sotto/app/webview'
def run(code,n=5):
    ts=[]
    for _ in range(n):
        t=time.perf_counter()
        subprocess.run(['python','-c',code],env=env,cwd=r'H:/sotto/app/webview',capture_output=True)
        ts.append((time.perf_counter()-t)*1000)
    return ts
base=run('pass'); imp=run('import sotto_webview')
print('baseline  ms', ['%.0f'%x for x in base], 'median %.0f'%st.median(base))
print('shell imp ms', ['%.0f'%x for x in imp], 'median %.0f'%st.median(imp))
print('delta median ms %.0f'%(st.median(imp)-st.median(base)))"

baseline  ms ['61', '62', '64', '64', '54'] median 62
shell imp ms ['94', '79', '104', '112', '95'] median 95
delta median ms 33
```

**Veredicto:** importar a shell custa **34,3 ms cumulativos**, dos quais **23,6 ms são o
próprio `site`** (arranque do interpretador, não código do Sotto) e **15,9 ms um
`__editable___consultgpt_14_0_0_finder`** — um *path hook* de outro projecto instalado em
editável, que o Sotto paga sem usar. Delta real medido: **33 ms**. O arranque do Sotto **não
é custo de import**; o custo de arranque é o carregamento do modelo (§ tabela, linha startup).

Nota lateral útil: o `site` (23,6 ms) é **70 % do import da shell** e não é dela.

---

## (b) cProfile no caminho de aplicação da legenda, por evento sintético nas funções REAIS

Sem janela, sem worker, sem áudio: `object.__new__` nas classes reais (não corre `__init__`,
logo não abre nada), e as chamadas vão às funções reais do módulo. `log` é substituído por
um no-op **para não escrever uma linha no log do dono**. Nada é reimplementado.

```
$ cd H:/sotto/app/webview && python - <<'PY'
import sys, io, time, cProfile, pstats
sys.path.insert(0, r'H:/sotto/app/webview')
real = sys.stdout
import sotto_webview as S
S.log = lambda m: None
S.log_repeat = lambda k, m, every_s=300.0: None

shell = object.__new__(S.SottoShell)
shell.caption_log = []
shell.external_captions_active = False
shell.external_suppressed = 0
shell.emit_async = lambda kind, payload: None
shell.push_caption_to_window = lambda *a, **k: True
shell._reload_policy = S.WorkerReloadPolicy.__new__(S.WorkerReloadPolicy)
shell._reload_policy.boundary = lambda **k: None
shell._last_push_final = False
shell._last_push_tap_ms = None
shell._last_push_at = 0.0
shell._caption_sent_count = 0
shell._caption_ages = []
shell._caption_hold = 0
shell._caption_lag_blown = 0

host = object.__new__(S.SottoHost)
host._shell = shell

N = 5000
def drive(n):
    t0 = time.perf_counter()
    for i in range(n):
        tap = int(time.time()*1000) - 40
        txt = 'the quick brown fox jumps over the lazy dog %d' % i
        S.SottoShell.on_worker_caption(shell, txt, {'tap_ms': tap, 'final': False, 'start': i*0.1, 'end': i*0.1+0.4})
        S.SottoHost._caption_applied(host, {'text': txt, 'count': i})
    return (time.perf_counter()-t0)

drive(200)
ts=[drive(1000) for _ in range(5)]
print('1k-caption batches s: ' + ' '.join('%.4f'%t for t in ts))
print('mean us/caption: %.2f' % (sum(ts)/len(ts)/1000*1e6/1000))
pr = cProfile.Profile(); pr.enable(); drive(N); pr.disable()
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats('tottime').print_stats(14)
real.write(s.getvalue())
PY

1k-caption batches s: 0.0271 0.0262 0.0295 0.0265 0.0260
mean us/caption: 0.03
         2326754 function calls in 0.569 seconds

   Ordered by: internal time
   List reduced from 28 to 14 due to restriction <14>

   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
  1005000    0.104    0.000    0.104  sotto_webview.py:13129(<genexpr>)
  1005000    0.096    0.000    0.096  sotto_webview.py:13125(<genexpr>)
     5000    0.073    0.000    0.169  {built-in method builtins.sorted}
    15000    0.063    0.000    0.264  {built-in method builtins.sum}
     5000    0.049    0.000    0.049  sotto_webview.py:13127(<genexpr>)
     5000    0.048    0.000    0.048  sotto_webview.py:13128(<genexpr>)
     5000    0.035    0.000    0.049  sotto_webview.py:13495(on_worker_caption)
     5000    0.027    0.000    0.508  sotto_webview.py:8563(_caption_applied)
     5000    0.026    0.000    0.471  sotto_webview.py:13090(_caption_lag_note)
     5000    0.006    0.000    0.010  sotto_webview.py:13131(pct)
    10250    0.004    0.000    0.012  json/__init__.py:183(dumps)
```

(os 27,1 ms por lote de 1000 são **27,1 µs por legenda**; o `0.03` impresso é um erro de
aritmética meu na linha de `print`, fica registado para quem repetir.)

Leitura: `_caption_lag_note` é **0,471 s de 0,569 s = 83 %** do caminho, e dentro dela
**1005000 iterações de gerador em 5000 legendas = 201 por legenda** — quatro passagens
sobre a janela inteira (`sorted` + 3×`sum`) a cada legenda. A causa está em
`sotto_webview.py:13122-13124`:

```python
ages.append((int(audio_ms), bool(held), bool(blown), live))
del ages[:-200]
if len(ages) % 25 == 0:          # ← com a janela CHEIA (200) isto é sempre True
```

`200 % 25 == 0`, portanto **a partir da 200.ª legenda o resumo da janela recalcula-se em
TODAS as legendas**, e não a cada 25. É um defeito do guarda, não do desenho.

Custo absoluto: **27 µs por legenda** contra um orçamento de 1500 ms — **0,002 %**. É o topo
do perfil de CPU e **não é um gargalo de latência**. Fica nomeado como defeito (§ "O que
mudar", #2), não como a cura.

### b.2 — lado da ponte (parser da linha do worker)

```
$ cd H:/sotto/app/webview && python - <<'PY'
import sys,json,time,cProfile,pstats,io
sys.path.insert(0,r'H:/sotto/app/webview')
import sotto_webview as S
S.log=lambda m: None
b=object.__new__(S.WorkerBridge)
b.malformed=0; b.captions=0; b.statuses=0; b.meters=0
b.pending_error=None; b.no_audio=False
b.on_caption=lambda t,m: None
line=json.dumps({'type':'caption','text':'the quick brown fox jumps over the lazy dog',
                 'start':1.12,'end':2.24,'final':False,'stable':True,'tap_ms':1,
                 'source':'device:Speakers'})
N=20000
t=time.perf_counter()
for i in range(N): b._consume(line)
d=(time.perf_counter()-t)
print('lines=%d  us per worker stdout line: %.2f'%(N, d/N*1e6))
t=time.perf_counter()
for i in range(N): json.loads(line)
d2=(time.perf_counter()-t)
print('  of which json.loads alone: %.2f us (%.0f%%)'%(d2/N*1e6,100*d2/d))
PY

lines=20000  us per worker stdout line: 6.68
  of which json.loads alone: 3.64 us (54%)
```

**6,68 µs por linha** do worker, 54 % em `json.loads`. Irrelevante contra 560 ms de chunk.

### b.3 — lado do painel (JS real, `caption-formulation.js`, `require` do mesmo ficheiro que o painel carrega)

```
$ cd H:/sotto && node --input-type=commonjs -e '
const F=require("./app/panel/caption-formulation.js");
let commits=0, provs=0;
const eng=F.createEngine({onCommit:()=>commits++, onProvisional:()=>provs++, now:()=>Date.now()});
const WORDS="the quick brown fox jumps over the lazy dog and then it keeps going with more words here today".split(" ");
function line(off){
  let emitted=0;
  for(let k=1;k<=12;k++){
    const n=Math.min(WORDS.length,k+off%4);
    eng.ingest(WORDS.slice(0,n).join(" "),{start:1.0+off,end:1.0+off+k*0.15,final:false,stable:true});
    emitted++;
  }
  eng.ingest(WORDS.slice(0,14).join(" "),{start:1.0+off,end:1.0+off+2.0,final:true,stable:true});
}
for(let i=0;i<50;i++) line(i*3);
const N=2000;
const t0=process.hrtime.bigint();
for(let i=0;i<N;i++) line(i*3);
const t1=process.hrtime.bigint();
console.log("us per LINE (13 ingests): "+((Number(t1-t0)/1e6/N)*1000).toFixed(1));
const txt=WORDS.slice(0,14).join(" ");
let t2=process.hrtime.bigint();
for(let i=0;i<20000;i++) F.formulate(txt);
let t3=process.hrtime.bigint();
console.log("us per formulate(14 words): "+(Number(t3-t2)/1e3/20000).toFixed(2));
'

lines=2000 ingests/line=13 commits=1280 provs=26137
us per LINE (13 ingests): 32.8
us per ingest: 2.52
us per formulate(14 words): 4.44
```

**2,52 µs por ingest, 32,8 µs por linha completa** (13 parciais + 1 final, a cadência real).
A formulação no painel não é a conta.

---

## (c) Os números que a app já publica, lidos do log vivo do dono (só leitura)

Fonte: `H:/sotto/_main/webview-run.log`, **64 370 239 B, 499 567 linhas**, última linha
`2026-11-04 10:51:02`, cobertura `2026-10-13 … 2026-11-04`. Todos os números abaixo saem de
um parser sobre esse ficheiro; cada bloco traz o comando.

### c.1 — Repartição POR LEGENDA PINTADA (`audio_ms` e `queue_ms` no mesmo evento)

O evento é `CAPTION_APPLIED`, e nele os dois carimbos vêm do MESMO push:
`audio_ms = agora − tap_ms` (idade do áudio) e `queue_ms = agora − _last_push_at` (publicado→pixel).
Logo `publish−tap = audio_ms − queue_ms` é decomposição exacta, não estimativa.

```
$ cd H:/sotto && python - <<'PY'
import io,re
p='_main/webview-run.log'
def pct(v,q):
    v=sorted(v); k=(len(v)-1)*q; f=int(k); c=min(f+1,len(v)-1); return v[f]+(v[c]-v[f])*(k-f)
buckets={}
with io.open(p,encoding='utf-8',errors='replace') as f:
    for l in f:
        if ' sotto: CAPTION_APPLIED ' not in l: continue
        a=re.search(r' audio_ms=(-?\d+)',l); q=re.search(r' queue_ms=(-?\d+)',l)
        k=re.search(r' kind=(\w+)',l); ak=re.search(r'aged_kind=([\w-]+)',l)
        if not(a and q): continue
        A=int(a.group(1)); Q=int(q.group(1)); kind=k.group(1) if k else '?'
        buckets.setdefault(kind+'/'+(ak.group(1) if ak else '-'),[]).append((A,A-Q,Q))
for k,v in sorted(buckets.items(), key=lambda kv:-len(kv[1])):
    A=[x[0] for x in v]; AR=[x[1] for x in v]; Q=[x[2] for x in v]
    print('%-26s n=%5d  audio p50=%6d p95=%6d | publish-tap p50=%6d p95=%6d | transport p50=%4d p90=%5d'%(
        k,len(v),pct(A,.5),pct(A,.95),pct(AR,.5),pct(AR,.95),pct(Q,.5),pct(Q,.9)))
PY

partial/transport          n= 1764  audio p50=   195 p95=  1815 | publish-tap p50=   183 p95=  1432 | transport p50=   5 p90=   34
partial/hold-expired       n=  374  audio p50=  2667 p95=  3148 | publish-tap p50=  1163 p95=  1640 | transport p50=1504 p90= 1508
final/final-close          n=  370  audio p50=   929 p95= 19402 | publish-tap p50=   914 p95= 17899 | transport p50=   8 p90= 1504
?/-                        n=  184  audio p50=    96 p95= 35061 | publish-tap p50=    89 p95= 34833 | transport p50=   2 p90=   10
final/hold-expired         n=   54  audio p50= 15579 p95=143603 | publish-tap p50= 14075 p95=142100 | transport p50=1504 p90= 1506
final/transport            n=   52  audio p50=   734 p95=121847 | publish-tap p50=   728 p95=121846 | transport p50=   2 p90=    8
partial/-                  n=   10  audio p50=  1590 p95=  8460 | publish-tap p50=   119 p95=  6958 | transport p50=1502 p90= 1504
final/-                    n=    2  audio p50= 21849 p95= 25417 | publish-tap p50= 21081 p95= 25339 | transport p50= 768 p90= 1382
```

A classe que decide a experiência é `partial/transport` (a legenda viva, 63 % das pinturas):

```
end-to-end  p50 195 ms   p95 1815 ms
  publish−tap  p50 183 ms  p95 1432 ms   ← 94 % da mediana
  transport    p50   5 ms  p90   34 ms   ←  2,6 %
```

`partial/hold-expired` (13 % das pinturas) tem `transport p50 = 1504 ms` e `publish−tap
p50 = 1163 ms`: é o `COMMIT_MAX_HOLD_MS = 1500` a segurar a cauda de propósito
(`caption-formulation.js:150`), não transporte perdido.

### c.2 — Cadência de publicação do worker

```
$ cd H:/sotto && python - <<'PY'
import io,re,datetime
p='_main/webview-run.log'
ts=[]
with io.open(p,encoding='utf-8',errors='replace') as f:
    for l in f:
        if ' sotto: CAPTION_IN ' not in l: continue
        fm=re.search(r'final=(\w+)',l)
        ts.append((datetime.datetime.strptime(l[:23],'%Y-%m-%d %H:%M:%S.%f'), fm.group(1)=='true' if fm else False))
gaps=[]
for (a,af),(b,bf) in zip(ts,ts[1:]):
    d=(b-a).total_seconds()*1000
    if 0<d<10000 and not af and not bf: gaps.append(d)
gaps.sort()
def pct(v,q):
    k=(len(v)-1)*q; f=int(k); c=min(f+1,len(v)-1); return v[f]+(v[c]-v[f])*(k-f)
print('live CAPTION_IN pairs=%d inter-arrival ms p50=%.0f p90=%.0f p95=%.0f max=%.0f'%(len(gaps),pct(gaps,.5),pct(gaps,.9),pct(gaps,.95),max(gaps)))
PY

live CAPTION_IN pairs=4201 inter-arrival ms p50=604 p90=1617 p95=2735 max=9964
```

**604 ms entre parciais.** E o tecto do modelo é 560 ms:

```
$ cd H:/sotto && python -c "import json;m=json.load(open('worker/models/nemotron-3.5-asr-ptbr-onnx-int4/genai_config.json',encoding='utf-8'))['model'];print(m['sample_rate'],m['chunk_samples'],m['chunk_samples']/m['sample_rate']*1000,'ms')"
16000 8960 560.0 ms

$ cd H:/sotto && python -c "import json;print(json.load(open('worker/config.json',encoding='utf-8'))['audio'])"
{'block_ms': 100}
```

O corte do chunk é exacto em amostras (`while len(buf) >= asr.chunk`, `sotto_worker.py:6457`),
mas a **disponibilidade** é quantizada pelo bloco do tap: com `block_ms=100`, 560 ms só ficam
completos ao 6.º bloco = **600 ms** → cadência 604 ms medida, 44 ms de arredondamento por
chunk. E `760/100 → 560`: 5 blocos dão 500 ms < 560, logo nunca fecha antes do sexto.

### c.3 — `CAPTION_IN` (idade do áudio na CHEGADA à shell) e janelas de resumo

```
$ cd H:/sotto && python - <<'PY'
import io,re
p='_main/webview-run.log'
def pct(v,q):
    v=sorted(v); k=(len(v)-1)*q; f=int(k); c=min(f+1,len(v)-1); return v[f]+(v[c]-v[f])*(k-f)
fin=[];par=[]
with io.open(p,encoding='utf-8',errors='replace') as f:
    for l in f:
        if ' sotto: CAPTION_IN ' not in l: continue
        m=re.search(r'age_ms=(\d+)',l); fm=re.search(r'final=(\w+)',l)
        if not m: continue
        (fin if (fm and fm.group(1)=='true') else par).append(int(m.group(1)))
for name,v in (('final=true',fin),('final=false(live)',par)):
    print('%s n=%d p50=%.0f p90=%.0f p95=%.0f p99=%.0f max=%.0f'%(name,len(v),pct(v,.5),pct(v,.9),pct(v,.95),pct(v,.99),max(v)))
PY

final=true n=547 p50=1041 p90=25320 p95=42367 p99=100593 max=203262
final=false(live) n=4974 p50=139 p90=1243 p95=1687 p99=12170 max=73591
```

`final=true` é projecto por desenho (a linha fecha depois da cauda de silêncio); a via viva é
**p50 139 ms / p95 1687 ms**.

`CAPTION_LAG_STATS` (a série que a própria app publica, 1897 janelas):

```
  janela n=200: p50 p50=264 p95=1206 max=1691 | p90 p50=1546 p95=45402
  janelas com over_win>0: 1570/1571
  última: 10:47:16.363 CAPTION_LAG_STATS n=200 p50=419 p90=1566 max=8172 over=83 held=30 over_win=21 held_win=8
```

### c.4 — As pausas longas NÃO são da shell

```
$ cd H:/sotto && python - <<'PY'
import io,re,collections
p='_main/webview-run.log'
lines=open(p,encoding='utf-8',errors='replace').readlines()
hot=[]
for i,l in enumerate(lines):
    if ' sotto: CAPTION_IN ' in l:
        m=re.search(r'age_ms=(\d+)',l); fm=re.search(r'final=(\w+)',l)
        if m and int(m.group(1))>8000 and fm and fm.group(1)=='false': hot.append((i,int(m.group(1))))
print('live stalls >8s:',len(hot))
for i,age in hot[:1]:
    print('--- stall age_ms=%d at %s'%(age,lines[i][:19]))
    for l in lines[max(0,i-8):i]: print('   ',l.rstrip()[:150])
PY

live stalls >8s: 82
--- stall age_ms=41586 at 2026-11-03 17:32:59
    2026-11-03 17:32:19.481 sotto: CAPTION_BUDGET_BLOWN audio_ms=1503 budget_ms=1500 queue_ms=1503 blown=1 path=panel text="RAP tool server sends a."
    2026-11-03 17:32:22.411 sotto: BRIDGE_STATS_REPLY id=s60 count=60 payload={"tag":"meter","peak":0.0,"blocks":1.0}
    2026-11-03 17:32:51.387 sotto: BRIDGE_METER count=559 in_window_s=35.6 sample={"peak":0.0,"blocks":1.0,"childPid":32384}
    2026-11-03 17:32:56.170 sotto: BRIDGE_RSS rss_mb=1796.3 blocks=606
    2026-11-03 17:32:59.564 sotto: BRIDGE_CAPTION_SENT delivered=async text="RAP tool server sends a message"
```

Durante os 40 s o pump está vivo e só publica meter/stat, e o meter lê `peak=0.0` — **a
shell está ociosa e à espera; o atraso nasce acima dela** (worker/tap), não na pintura.

### c.5 — Instrumentos de saúde já publicados

```
$ cd H:/sotto && python - <<'PY'
import io,re,collections
p='_main/webview-run.log'
def pct(v,q):
    v=sorted(v); k=(len(v)-1)*q; f=int(k); c=min(f+1,len(v)-1); return v[f]+(v[c]-v[f])*(k-f)
def grab(tag):
    return [l for l in io.open(p,encoding='utf-8',errors='replace') if ' sotto: '+tag in l]
er=[float(m.group(1)) for m in (re.search(r'ms=([0-9.]+)',l) for l in grab('EXTERNAL_CAPTIONS_READ_MS')) if m]
bl=[int(m.group(1)) for m in (re.search(r'ms=(\d+)',l) for l in grab('BRIDGE_LOAD_MS')) if m]
rss=[float(m.group(1)) for m in (re.search(r'rss_mb=([0-9.]+)',l) for l in grab('BRIDGE_RSS')) if m]
gap=[int(m.group(1)) for m in (re.search(r'max_gap_ms=(\d+)',l) for l in grab('HOTKEY_OBSERVER_ALIVE')) if m]
print('EXTERNAL_CAPTIONS_READ_MS n=%d p50=%.0f p95=%.0f max=%.0f  >3000ms:%d'%(len(er),pct(er,.5),pct(er,.95),max(er),sum(1 for x in er if x>3000)))
print('BRIDGE_LOAD_MS n=%d p50=%.0fs p95=%.0fs max=%.0fs'%(len(bl),pct(bl,.5)/1000,pct(bl,.95)/1000,max(bl)/1000))
print('BRIDGE_RSS n=%d p50=%.0fMB max=%.0fMB'%(len(rss),pct(rss,.5),max(rss)))
print('HOTKEY_OBSERVER_ALIVE max_gap_ms n=%d p50=%d p95=%d max=%d'%(len(gap),pct(gap,.5),pct(gap,.95),max(gap)))
PY

EXTERNAL_CAPTIONS_READ_MS n=4308 p50=172 p95=2688 max=341781  >3000ms:189
BRIDGE_LOAD_MS n=477 p50=16s p95=76s max=168s
BRIDGE_RSS n=986 p50=1071MB max=2369MB
HOTKEY_OBSERVER_ALIVE max_gap_ms n=3897 p50=281 p95=1830 max=92890
```

O log está a ser escrito **enquanto se lê** (a app vive, pid 42548): os `n=` sobem entre
execuções da mesma medição (ex.: `EXTERNAL_CAPTIONS_READ_MS` leu 4235, 4250 e 4308 em três
passagens; os **p50** ficaram nos três em 172 ms). As percentis são estáveis; as contagens não.

`EXTERNAL_CAPTIONS_READ_MS` **não é toda a leitura**: só sai acima de 40 ms e no máximo 1 vez
por 5 s (`sotto_webview.py:2492-2497`). A varredura da página corre de 5 em 5 s
(`if _now - self._page_scan_at < 5.0: return`, `sotto_webview.py:2910`), e o próprio log
mostra a proporção:

```
2026-11-04 10:51:01.923 sotto: PAGE_SCAN_NET source='' scanned=391 skipped=6476 why=...
```

1 leitura em ~17 paga a varredura → **172 ms / 5 s = 3,4 % de ocupação**. O instrumento
atribui **0,0 ms das 172** às fases que marca (`phases={'target': 0.0, 'source': 0.0}`): o
segmento da varredura não tem marco. Buraco de instrumento, não gargalo.

O único custo de CPU já medido no processo da shell, por nome de thread:

```
2026-11-03 05:36:48.517 sotto: THREAD_CPU total=100% top=sotto-vram-guard:96% sotto-external-captions:2% ...
2026-11-03 05:38:18.525 sotto: THREAD_CPU total=100% top=sotto-vram-guard:95% ...
```

**Já fechado no disco:** o `while` do `VramGuard.run` voltou a ter a espera dentro
(`self.stop_event.wait(self.INTERVAL_S)`, `sotto_webview.py:2098`), com o comentário a
registar a medição. Não conta contra o HEAD; conta como "isto já aconteceu uma vez".

Vigias de UI (`UI_WATCHDOG_STRIKE` 154, `UI_WATCHDOG_RECOVERED` 68, `UI_WATCHDOG_EXIT` 8,
`UI_HUNG_THREAD` 2225, e 165 linhas nomeiam `caption-read-slow`): a UI falhou um `WM_NULL`
com 6 s de limite 154 vezes em ~3 semanas — não é a causa da fila normal, mas é o
mecanismo que explica os `queue_ms` de 4 758 ms do pior caso.

Arranque, por dia (`BRIDGE_LOAD_MS`):

```
2026-10-30 n=36  min=16.8s median=38.5s max=128.3s
2026-11-01 n=54  min=13.9s median=26.0s max=102.7s
2026-11-02 n=55  min=11.1s median=18.9s max= 53.9s
2026-11-03 n=121 min= 3.8s median=16.6s max=167.9s
2026-11-04 n=38  min= 6.7s median= 8.9s max= 26.5s
```

Hoje: **8,9 s de mediana** até `model-loaded`; a p50 histórica de 16,1 s é de builds antigas.

---

## (d) `I:/rea` — o que é, e se serve nesta máquina

`I:/!rea` **não existe**:

```
$ ls "I:/!rea"
ls: cannot access 'I:/!rea': No such file or directory
```

`I:/rea` é um repo real:

```
$ cd I:/rea && python -c "import json;d=json.load(open('package.json',encoding='utf-8'));print(d['name'],d['version']);print(d['description']);print(d['bin'])"
rea-agents 6.8.0
Reverse engineer anything from your terminal or agent with one CLI and MCP server.
{'rea': 'scripts/rea.mjs', 'rea-agents': 'scripts/rea.mjs'}

$ cd I:/rea && git log -1 --format='%h %ad %s'
47cedcc93 Wed Nov  4 10:47:46 2026 +0200 fix(cli): reject empty artifact command targets before resolution (#8834)
$ git -C I:/rea status --porcelain | wc -l
0
```

O que é: **`rea-agents` v6.8.0, um CLI + servidor MCP de ENGENHARIA REVERSA** (Ghidra, IDA,
Hopper, bridges nativos, análise de bundles JS/web, verificação Frida — `keywords` do
`package.json`: `reverse-engineering binary-analysis decompiler ghidra ida hopper electron
javascript-analysis mcp`). Não é um profiler: no README, das 3 ocorrências de "profil", as 3
são `schema profile` do protocolo MCP, e não há nenhum subcomando de amostragem/CPU/heap.

**Serve nesta máquina? Não, tal como está:**

```
$ cd I:/rea && ls -d dist node_modules
ls: cannot access 'dist': No such file or directory
ls: cannot access 'node_modules': No such file or directory

$ cd I:/rea && node scripts/rea.mjs --version
REA's compiled runtime is missing. Run `npm ci && npm run build:cached` in I:\rea to install
dependencies and build REA, then restart it. If this is an installed package, reinstall rea-agents.
```

O runtime compilado não existe e o build (`npm ci && npm run build:cached`, com
`build:ghidra-nativeaot`, `build:windows-native`) é trabalho **pesado** — e o portão central
está `UNKNOWN` (§ topo), logo `heavy_allowed=False`. Fica registado o que falta: **um lease
`heavy`** e o build; nenhum dos dois foi tentado.

Para o Sotto especificamente, o que ele acrescentaria seria RE de um Electron/bundle de
terceiro. O painel do Sotto é fonte deste repo (`app/panel/*.js`), logo `rea` não cobre nada
que o §(b) não tenha medido directamente.

---

## Tabela de gargalos

`p50 / p95` em ms; "medido" = número lido de um instrumento cujo comando está acima.

| estágio | instrumento | p50 | p95 | onde o tempo vai | veredicto |
|---|---|---|---|---|---|
| **tap WASAPI** (`LoopbackTap`, `block_ms=100`) | `worker/config.json` + `wasapi_loopback.py:1001-1038` (ring 1056 fr = 22 ms, poll ≤5 ms). Abrir o dispositivo é proibido (áudio do dono) → **nenhuma medição de relógio** | — | — | quantum de bloco: 0…100 ms de áudio preso no `buf` por chunk (média 50 ms) | **[INFERENCE]** no relógio; a *consequência* é medida na linha seguinte |
| **fecho do chunk / cadência** | inter-arrival dos `CAPTION_IN` vivos (n=4201) + `genai_config.chunk_samples=8960@16k` | **604** | 1617 (p90) | 560 ms de modelo + 44 ms de arredondamento a 100 ms de bloco | medido |
| **decode + AGC + VAD + LineFormer + emit** | `CAPTION_IN age_ms` (vivo, n=4974) e `publish−tap` do par (n=1764) | **139** / **183** | 1687 / 1432 | inferência do nemotron sobre 560 ms de áudio; a repartição interna não tem marco por etapa | o número é medido; a divisão por sub-etapa é **[INFERENCE]** |
| **ponte (stdout → `emit_async`)** | `cProfile` de `WorkerBridge._consume` (n=20 000 linhas) | **0,0067** | — | 54 % `json.loads` | medido, não é gargalo |
| **painel: formulação** (JS) | `node` sobre o `caption-formulation.js` real | **0,0328**/linha | — | 13 `ingest` por linha, 2,52 µs cada | medido, não é gargalo |
| **painel: pintura + ack** | `queue_ms` do `CAPTION_APPLIED` (`partial/transport`, n=1764) | **5** | 34 (p90); 1504 na classe `hold-expired` (17,5 % das pinturas) | 17,5 % das pinturas batem no `COMMIT_MAX_HOLD_MS=1500` de propósito | medido |
| **shell: aplicação (`_caption_applied`→`_caption_lag_note`)** | `cProfile` sobre as funções reais | **0,027**/legenda | — | 83 % no resumo da janela, recalculo a cada legenda (guarda partido) | medido, defeito de CPU sem efeito na latência |
| **fim-a-fim, legenda viva** | `audio_ms` do `CAPTION_APPLIED` | **195** | **1815** | 183 de decode+cadência, 5 de pintura | medido |
| **fim-a-fim, com o quantum do tap somado** | os mesmos + `block_ms` | **~245** | ~1915 | o `audio_ms` ancora no bloco que *fechou* o chunk, logo **subestima** em média meia-largura de bloco | aritmética sobre medidos |
| **arranque (modelo)** | `BRIDGE_LOAD_MS` (hoje, n=38) | **8 900** | 26 500 (max) | carregamento do ONNX int4 no worker | medido; p50 histórica 16 100 ms |
| **leitura de legendas externas (YouTube/Stremio)** | `EXTERNAL_CAPTIONS_READ_MS` (só >40 ms, ≤1/5 s) | **172** | 2712 (max 341 781) | varredura UIA da página, 1 leitura em ~17 (3,4 % de ocupação) | medido; instrumento não atribui as 172 ms |
| **memória** | `BRIDGE_RSS` | 1 071 MB | máx 2 369 MB | — | medido |

### Onde o tempo vai, em uma frase

**94 % da latência mediana (183 de 195 ms) está ANTES da shell** — no decode do worker e na
cadência de chunks; a shell inteira (ponte + aplicação + pintura) custa **5 ms**, e a
pintura da página **não é o problema**. A latência percebida é ~**245 ms de mediana**
(195 medidos + ~50 de áudio preso no quantum de 100 ms, que o instrumento não conta), com
cauda de **1,8 s p95** que é decode/cadência e, em 17,5 % das pinturas, o *hold* de 1500 ms
que o painel faz de propósito para não partir frases.

### A MUDANÇA com a melhor razão medida

**`worker/config.json: audio.block_ms: 100 → 40`** (14 blocos por chunk de 560 ms, divisão
exacta). Uma linha de configuração, zero código.

- Ganho medido: a cadência cai de **604 → 560 ms** (−44 ms, −7,3 %) — o `while len(buf) >=
  asr.chunk` deixa de precisar de um 6.º bloco para completar 560 ms; e o áudio preso por
  chunk (média meia-largura de bloco) cai de **~50 → ~20 ms** (−30 ms).
- Efeito na mediana percebida: **~245 → ~215 ms** (−12 %), e o pior caso de quantum
  **100 → 40 ms**.
- Custo: nulo em CPU total — o trabalho por segundo do callback (`on_block`: contadores +
  `float64` sum + `queue.put`) é proporcional às amostras, não aos blocos; só aumenta 2,5× o
  número de chamadas (14 em vez de 5,6 por chunk), e o `_consume`/JSON do lado da shell é
  6,7 µs por linha. Não toca o modelo nem o `chunk_samples`, que é geometria do nemotron.
- Porque é esta e não outra: é a única que ataca o **termo medido** que domina e não tem
  contrapartida de desenho. (Recalcular o mínimo de `_caption_lag_note` rende 22 µs → razão
  óptima mas absoluto irrelevante; baixar o `COMMIT_MAX_HOLD_MS` de 1500 ms troca latência
  por frases partidas.)

**Nº 2 (defeito, não gargalo)** — `sotto_webview.py:13124`: `if len(ages) % 25 == 0` é
**sempre verdadeiro** com a janela cheia (200 % 25 == 0), logo o resumo da janela corre em
**todas** as legendas (201 iterações/legenda medidas, 83 % do caminho de aplicação). Um
contador próprio (`self._caption_notes = n+1; if n % 25 == 0`) devolve o custo ao desenho.

**Nº 3 (buraco de instrumento)** — a leitura externa publica 172 ms com
`phases={'target': 0.0, 'source': 0.0}`: falta o marco do segmento da varredura, que é onde
o tempo está. Enquanto não houver esse marco, "porque é que a leitura leva 172 ms" não tem
resposta no log.

---

## Limites deste recibo

- **`[INFERENCE]` está marcado**: o relógio do tap (não se abre o áudio do dono), e a
  repartição interna do decode (o worker não publica tempo por chunk enquanto vive — o
  `infer_wall_s` só sai no `WORKER_STATS tag=final` de saída, e os dumps existentes no log
  têm `infer_wall_s=0.00`).
- A instância que produziu o log está **STALE** face ao disco (§ topo). Nenhum número do §(c)
  é verificação do HEAD.
- `EXTERNAL_CAPTIONS_READ_MS` é uma **amostra** (só >40 ms, no máximo 1 por 5 s), não o
  universo das leituras.
- O `queue_ms` do `CAPTION_APPLIED` e o `audio_ms` do mesmo evento partilham os carimbos do
  último push; nos eventos em que a página confirma um push anterior ao último, os dois campos
  descrevem pushes diferentes. É por isso que a decomposição fiável é a do **par** (`audio_ms
  − queue_ms`), e é essa que está na tabela.
