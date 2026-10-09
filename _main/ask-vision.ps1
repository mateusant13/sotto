# ask-vision.ps1 — pergunta a OUTRO harness sobre uma imagem.
#
# PORQUE ISTO EXISTE: o harness do DSH não passa imagens ao modelo (o `read_image`
# é recusado por capacidade), portanto o agente principal é cego a capturas de ecrã.
# O `opencode` aceita anexos (`-f`) e tem modelos multimodais autenticados.
#
# NOTA MEDIDA (2026-10-08): o único provider autenticado no opencode desta máquina é
# o `google` (`.local\share\opencode\auth.json` → `google`). NÃO há DeepSeek lá.
# Modelos de visão disponíveis: google/gemini-3.x-flash, google/gemini-2.5-flash.
#
# USO:
#   pwsh -File H:\sotto\_main\ask-vision.ps1 -Image H:\sotto\_main\_img-panel-dono-20261008.png
#   pwsh -File ... -Model google/gemini-2.5-flash -Prompt "descreve so o rodape"
#
# NUNCA abre janela visível: herda a consola escondida de quem o chama e escreve
# tudo para ficheiro.

param(
  [Parameter(Mandatory = $true)][string]$Image,
  [string]$Model = 'google/gemini-3.5-flash',
  [string]$Prompt = '',
  [string]$Out = ''
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path -LiteralPath $Image)) { throw "ask-vision: imagem nao existe: $Image" }
$imgItem = Get-Item -LiteralPath $Image
if ($imgItem.Length -eq 0) { throw "ask-vision: imagem tem 0 bytes: $Image" }

# O prompt pede FACTOS ESTRUTURAIS e proibe invenção — porque o objectivo é
# diagnosticar layout, não receber uma impressão agradável.
if (-not $Prompt) {
  $Prompt = @'
Olha para a imagem anexada. E a captura de um painel de aplicacao de legendas ao vivo (380x900 px, tema escuro). Preciso de FACTOS, nao de impressoes. Responde em portugues, por pontos:

1. ZONAS: o que aparece em cada faixa vertical da imagem, de cima para baixo, com a altura aproximada de cada uma em pixeis.
2. TEXTO DE PROGRAMADOR: existe algum texto que pareca ser codigo, comentario de programador, nome de classe CSS ou prosa tecnica — em vez de transcricao de fala? Se existir, TRANSCREVE-O VERBATIM, incluindo simbolos como <!-- --> ou -->.
3. BOTOES: onde estao, quantos sao, e o que esta escrito em cada um. Algum botao se SOBREPOE a texto ou a outro elemento?
4. DEFEITOS: algum texto cortado, encostado a borda, sobreposto, desalinhado ou com contraste ilegivel? Descreve onde.
5. CORES: as cores dominantes, e o que esta destacado (por exemplo, se um horario aparece em amarelo e outros em cinza).
6. Se algo nao for legivel, escreve "ilegivel" — NAO inventes nem completes por deducao.
'@
}

if (-not $Out) {
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $Out = Join-Path $PSScriptRoot "ask-vision-out-$stamp.txt"
}

# Direccao de trabalho propria: o opencode nao deve indexar o repositorio do dono.
$work = Join-Path $PSScriptRoot 'opencode-vision'
New-Item -ItemType Directory -Force -Path $work | Out-Null

# `--pure` desliga plugins externos (o MCP `lean-ctx` nao interessa a uma pergunta
# sobre uma imagem, e so acrescenta modos de falha).
$started = Get-Date
# ARMADILHA MEDIDA 2026-10-08: `-f` e uma opcao de LISTA (yargs `[array]`) e
# ENGOLE os argumentos posicionais que vierem depois dela — na primeira versao
# deste script o prompt foi lido como um SEGUNDO FICHEIRO e o opencode respondeu
# "Error: File not found: Olha para a imagem anexada...". A mensagem vai PRIMEIRO
# e o `-f` fica no FIM, sem nada depois para ele comer.
& opencode run --pure --dir $work -m $Model $Prompt -f $Image > $Out 2>&1
$rc = $LASTEXITCODE
$secs = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)

"ask-vision: modelo=$Model rc=$rc segundos=$secs"
"ask-vision: imagem=$Image ($($imgItem.Length) B)"
"ask-vision: saida=$Out ($((Get-Item -LiteralPath $Out).Length) B)"
"---- RESPOSTA ----"
Get-Content -LiteralPath $Out -Raw
