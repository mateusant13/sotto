# O ERRO VERMELHO NA TELA: `0x8889000A` passa a ser uma frase que diz o que fazer

## O que ele viu, e o que ele disse

A linha que o painel pintava, com um ponto vermelho:

    Worker error at open-stream - WasapiError: Initialize(SHARED|LOOPBACK) failed:
    <no description> (0x8889000A)

E ele: *"que nojeira e essa mano? ate quando tu vai fazer essas coisas?"*

**Um codigo hexadecimal na tela do dono nao e um diagnostico, e um segredo.** E ele JA
tinha mandado arrumar isto, em 2026-10-14, verbatim: *"sotto ta reclamando de coisa nao
carregada, com erro vermelho. arruma"*.

## O que o codigo quer dizer, e porque e que isto importa

`0x8889000A` e `AUDCLNT_E_DEVICE_IN_USE`: **o dispositivo de audio ja esta ocupado por outro
programa.** A acao que resolve e uma so -- fechar quem o esta a segurar, ou escolher outro
dispositivo -- e **nao esta escrita em lado nenhum do hexadecimal**. O dono via um erro sem
saber o que fazer com ele.

## A tabela, e a decisao de nao inventar

    HRESULT_AUDIO_READINGS = {
      '0x88890001': o dispositivo nao foi inicializado; tentar outra vez
      '0x88890004': o dispositivo desapareceu (desligado ou desactivado)
      '0x88890008': o dispositivo nao suporta o formato que o Sotto precisa
      '0x8889000A': o dispositivo esta OCUPADO -- fechar quem o segura;
      '0x8889000B': esse tamanho de buffer nao e suportado
      '0x88890010': nao ha dispositivo nenhum -- ver as definicoes de som do Windows
    }

E `human_audio_error(detail)` **devolve `None` quando o codigo nao esta na tabela.** Isso e
deliberado: um erro desconhecido continua a ser mostrado como veio. **Inventar uma
explicacao para um codigo que nao conhecemos e pior do que o codigo.**

## Testado em processo, sem lancar nada

    importlib sobre o shell real, tres casos:
      0x8889000A  -> TRADUZ
      0x88890010  -> TRADUZ
      desconhecido -> PASSA CRU

`py_compile` rc=0, 551 749 B. O detalhe CRU continua a ir inteiro para o LOG
(`BRIDGE_STATUS_ERROR`), portanto quem diagnostica nao perde nada. **O que muda e o que o
DONO LE.**

## E UM ERRO MEU, o segundo igual hoje, que vale mais do que a correccao

Ao inserir a tabela escrevi `L.splice(i, 0, ...tabela)` com `tabela` a ser uma **STRING**
(eu tinha feito `.join("\r\n")` antes). **O spread de uma string insere UM CARACTERE POR
LINHA:** o ficheiro passou de 10 290 para 12 914 linhas e deixou de ser Python.

Apanhei-o ao verificar (`tem tabela: false` depois de a ter "inserido"), restaurei com
`git checkout --` e confirmei que as SEIS correccoes anteriores continuavam la: caption
window, loaded+Invoke, live ligado, tecto do reinicio, diagnostico do arrasto, marca do
duplicado. **Todas.** E refiz com ARRAY.

**E a segunda vez hoje que o mesmo descuido me custa um ficheiro inteiro.** A diferenca e
que desta vez verifiquei em vez de seguir em frente -- e a verificacao e que o apanhou, nao
o `py_compile`, que eu nem cheguei a correr antes de olhar.
