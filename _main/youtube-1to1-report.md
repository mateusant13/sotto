video            : WdaHAGRBB6s
payload do player: H:\sotto\_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3
payload sha256   : 9806e76a435a8af8f8f6c98745579e5e14d08f57b6b85c23dc66286b461d67ab
cache servida    : H:\sotto\_cache\youtube-captions\WdaHAGRBB6s.jsonl
cues comparados  : served
linhas do player : 19  |  cues servidos: 19  |  amostras: 677  (passo 0.05s)
janela           : rcRows=2 (YouTube) | 2 (Sotto)
caminho          : live-window

elemento                 veredicto  medicao
source-is-youtube        GREEN      payload do player (events+wpWinPositions+wireMagic)=True | cues servidos == parse do payload=True
capacity-from-payload    GREEN      rcRows=2 no payload | o Sotto desenha 2
words-1to1               GREEN      amostras com texto diferente: 0/677
linebreaks-1to1          GREEN      amostras com numero de linhas diferente: 0/677
timing-1to1              GREEN      transicoes do player sem par: 0/18 | transicoes do Sotto a mais: 0/18 (tolerancia 0.05s)
word-reveal-1to1         GREEN      prefixo revelado diferente: 0/677 amostras | segmentos com tOffsetMs no payload: 69 | palavras com relogio nos cues servidos: 88

(nenhuma divergencia de desenho em 677 amostras)
