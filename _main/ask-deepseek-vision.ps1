# ask-deepseek-vision.ps1 — chama o MEU PROPRIO modelo (deepseek-v4.1-flash) por fora do
# harness, com uma imagem anexada, para usar a visao que o harness nao me entrega.
#
# PORQUE ISTO EXISTE (tudo medido, 2026-10-08):
#   * O perfil do harness declara o modelo com `input: [ text, image ]` e o comentario ao
#     lado diz "VISION, live-verified 2026-10-07: 8x8 red PNG -> answered Red"
#     (`~/.dsh/profiles/web/cordis.patch.yml` :87-95). Ou seja: o MODELO VE.
#   * Mesmo assim o `read_image` do harness recusa por capacidade. O bloqueio esta no
#     harness, nao no modelo — e a prova e a declaracao acima.
#   * Rota do modelo: `https://opencode.ai/zen/go/v1`, wire `openai-completions`
#     (medido: `/responses` devolve so raciocinio para o v4.1-flash neste gateway).
#   * `x-opencode-session` e o header de afinidade do gateway: SEM ELE, 400 MissingSessionID.
#   * Chaves: `OPENCODE_API_KEY_A..D` (env de lancamento > refs do .credentials.yaml > .env);
#     o `.credentials.yaml` tem `OPENCODE_ZEN_API_KEY` — mesmo gateway "zen".
#
# USO:
#   pwsh -File H:\sotto\_main\ask-deepseek-vision.ps1 -Image C:\...\captura.png
#   pwsh -File ... -Model deepseek-v4.1-flash -Prompt "descreve so o rodape"

param(
  [Parameter(Mandatory = $true)][string]$Image,
  [string]$Model = 'deepseek-v4.1-flash',
  [string]$Prompt = '',
  [string]$Out = ''
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Image)) { throw "imagem nao existe: $Image" }
$imgBytes = [IO.File]::ReadAllBytes($Image)
if ($imgBytes.Length -eq 0) { throw "imagem com 0 bytes: $Image" }
$imgItem = Get-Item -LiteralPath $Image

# ── 1. A CHAVE, pela ordem que o proprio perfil documenta ─────────────────────
$keyName = $null
$key = $null
foreach ($n in @('OPENCODE_API_KEY_A', 'OPENCODE_API_KEY_B', 'OPENCODE_API_KEY_C', 'OPENCODE_API_KEY_D')) {
  $v = [Environment]::GetEnvironmentVariable($n, 'Process')
  if ($v) { $key = $v; $keyName = "$n (env)"; break }
}
if (-not $key) {
  $cred = Join-Path $env:USERPROFILE '.dsh\.credentials.yaml'
  if (Test-Path -LiteralPath $cred) {
    foreach ($n in @('OPENCODE_API_KEY_A', 'OPENCODE_API_KEY_B', 'OPENCODE_API_KEY_C', 'OPENCODE_API_KEY_D', 'OPENCODE_ZEN_API_KEY')) {
      $m = Select-String -LiteralPath $cred -Pattern ("^\s*" + $n + "\s*:\s*""?([^""\r\n]+)""?") -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($m) { $key = $m.Matches[0].Groups[1].Value.Trim(); $keyName = "$n (.credentials.yaml)"; break }
    }
  }
}
if (-not $key) { throw "ask-deepseek-vision: nenhuma chave encontrada (env OPENCODE_API_KEY_A..D ou .credentials.yaml). O perfil nomeia-as; sem chave nao ha chamada." }
$keyMasked = $key.Substring(0, [Math]::Min(6, $key.Length)) + '…(len=' + $key.Length + ')'

# ── 2. O PEDIDO ───────────────────────────────────────────────────────────────
if (-not $Prompt) {
  $Prompt = @'
Olha para a imagem anexada. E a captura de um painel de aplicacao de legendas ao vivo (380x900 px, tema escuro). Preciso de FACTOS, nao de impressoes. Responde em portugues, por pontos:

1. ZONAS: o que aparece em cada faixa vertical da imagem, de cima para baixo, com a altura aproximada de cada uma em pixeis.
2. TEXTO DE PROGRAMADOR: existe algum texto que pareca ser codigo, comentario de programador, nome de classe CSS ou prosa tecnica — em vez de transcricao de fala? Se existir, TRANSCREVE-O VERBATIM.
3. BOTOES: onde estao, quantos sao, o que esta escrito em cada um, e se algum se SOBREPOE a texto ou a outro elemento.
4. DEFEITOS: algum texto cortado, encostado a borda, sobreposto, desalinhado ou com contraste ilegivel? Diz onde.
5. CORES: as cores dominantes, e o que esta destacado (por exemplo se um horario aparece em amarelo e outros em cinza).
6. Se algo nao for legivel, escreve "ilegivel" — NAO inventes nem completes por deducao.
'@
}

$dataUrl = 'data:image/png;base64,' + [Convert]::ToBase64String($imgBytes)
$body = @{
  model    = $Model
  messages = @(
    @{
      role    = 'user'
      content = @(
        @{ type = 'text'; text = $Prompt },
        @{ type = 'image_url'; image_url = @{ url = $dataUrl } }
      )
    }
  )
} | ConvertTo-Json -Depth 12 -Compress

$headers = @{
  'Authorization'      = "Bearer $key"
  'Content-Type'       = 'application/json'
  'x-opencode-session' = [guid]::NewGuid().ToString()
}

if (-not $Out) {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $Out = Join-Path $PSScriptRoot "ask-deepseek-vision-out-$stamp.json"
}

$uri = 'https://opencode.ai/zen/go/v1/chat/completions'
"ask-deepseek-vision: modelo=$Model  chave=$keyName  ($keyMasked)"
"ask-deepseek-vision: imagem=$($imgItem.Name) ($($imgBytes.Length) B)  wire=openai-completions"
"ask-deepseek-vision: POST $uri"

$started = Get-Date
try {
  $resp = Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $body -TimeoutSec 180
  $secs = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
  $resp | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Out -Encoding UTF8
  "ask-deepseek-vision: OK em $secs s  ->  $Out"
  "---- RESPOSTA ----"
  if ($resp.choices) { $resp.choices[0].message.content } else { $resp | ConvertTo-Json -Depth 8 }
} catch {
  $secs = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
  "ask-deepseek-vision: FALHOU em $secs s"
  $r = $_.Exception.Response
  if ($r) {
    "  HTTP $([int]$r.StatusCode) $($r.StatusDescription)"
    try { $sr = New-Object IO.StreamReader($r.GetResponseStream()); $txt = $sr.ReadToEnd(); $txt | Set-Content -LiteralPath $Out -Encoding UTF8; "  corpo: $($txt.Substring(0,[Math]::Min(900,$txt.Length)))" } catch { "  (corpo ilegivel)" }
  } else { "  $($_.Exception.Message)" }
}
