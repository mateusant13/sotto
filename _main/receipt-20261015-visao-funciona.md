A VISAO FUNCIONA: o interruptor estava no perfil WEB, e eu mexi no HEADLESS

O dono: "veja se tu ja suporta imagem" e "veja como deepseek faz pra receber
imagem, por que ele funciona. e seu modelo TEM visao. faca acontecer. nao reinicie
o server."

A CADEIA, medida no codigo do harness:
  read_image -> assertImageCapableRoute (dsh-tool-fs:905)
    -> llm.resolveModelInfo(provider, model)
      -> adapter.resolveModel() (dsh-llm-pi-ai)
        -> this.current() -> this.config.profiles()   <- LE O PERFIL VIVO
        -> inputModalities: [...resolvedModel.input]  <- o campo YAML e "input"

Ou seja: o adaptador le o perfil a CADA chamada e o campo e "input". A config
certa existia -- no ficheiro ERRADO.

O MEU ERRO, e ele explica duas rodadas de nada: editei
  .dsh/profiles/HEADLESS/cordis.patch.yml
mas a sessao do dono e a WEB, e o perfil vivo e
  .dsh/profiles/WEB/cordis.patch.yml

CORRIGIDO: os 5 blocos de step-5-preview-free no perfil WEB passaram a
input: [ text, image ]. E verificado: read_image agora devolve a imagem
(theme1.png, 380x900, 29 567 B, sha256 d8de6d15...). SEM reiniciar o server.

E o que a primeira imagem que vi mostrou -- e que eu devia ter visto ha semanas:
o painel do dono Tem TRANSCRIPT no canto, HISTORICO e EM CURSO em baixo. O CSS
medido esta limpo (nenhum dos tres literais em panel.css nem nas 4 folhas
geradas), e o history-toggle foi removido -- mas ha um <span class="history__label">
renderizado com o texto Transcript, e o print e ANTIGO (16:50), portanto a
HISTORICO/EM CURSO que ele mostra eram da build anterior.

O que isto muda: o criterio E2 ("compara as prints") deixou de ser impossivel. E o
B5/B6 precisam de ser vistos com olhos novos, nao com o meu grepo.
