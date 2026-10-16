# F6 FECHADO E VERIFICADO: o hexadecimal saiu do CORPO da UI

## O que ele via -- e era o que o audit dos dialogos mediu

    stage=capture-open detail=WasapiError: AUDCLNT_E_DEVICE_IN_USE (0x8889000A)
    device=Alto-falantes api=MME peak=0.000122

**O hexadecimal CRU na tela do dono.** A tabela `HRESULT_AUDIO_READINGS` que eu escrevi
estava ligada so ao RODAPE (`worker_status_text`), e `worker_status_body` -- o irmao ao lado,
que enche o CORPO do placeholder -- juntava os campos como vieram (`sotto_webview.py:742-746`).
**Metade da cura estava feita e eu chamei-lhe feita.**

## A correccao, nos dois sitios

O corpo traduz o `detail` pela mesma tabela; e o fallback do rodape tambem.

## Medido em processo, sem lancar nada

    CORPO:  stage=capture-open detail=THE AUDIO DEVICE IS ALREADY IN USE BY ANOTHER
            PROGRAM, SO SOTTO COULD NOT OPEN IT. CLOSE WHATEVER IS HOLDING IT -- OR
            CHOOSE ANOTHER DEVICE -- AND PRESS ALT+C. device=Alto-falantes api=MME
            peak=0.000122

    RODAPE: Sotto could not start listening - The audio device is already in use...

    DESCONHECIDO: stage=x detail=SomeUnknownError: thing (0xDEADBEEF)

**E o terceiro caso e tao importante quanto os outros dois:** um codigo que NAO esta na
tabela continua a passar cru. Inventar uma explicacao para o que nao conhecemos e pior do que
o codigo -- e o detalhe cru continua inteiro no log, para quem diagnostica.

`py_compile` rc=0, 555 754 B.
