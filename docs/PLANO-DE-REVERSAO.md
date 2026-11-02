# Plano de reversão e backup — versão 1.9.31 (editor de notícias com chamada e matéria)

## O que mudou no banco de dados (somente aditivo)
- `noticias`: `chamada_titulo`, `chamada_resumo`, `chamada_imagem`, `chamada_legenda`, `chamada_alt`, `chamada_formato`, `chamada_visivel`, `so_pagina`
- `cartao_conteudo`: `materia_titulo`, `materia_html`
- `lateral`: `corpo_html`, `materia_titulo`, `materia_html`

Nenhuma coluna ou registro antigo foi alterado ou apagado. Campos de chamada vazios usam os da matéria (título, resumo, capa), então notícias antigas continuam iguais.

## Antes de atualizar
1. Aba **Backup** do admin → gerar backup (ou copie `dados.db` e a pasta `static/uploads`).
2. Não altere `secret.key`.

## Reverter
1. Restaure os arquivos da versão anterior (`sudo ./atualizar.sh` com o zip antigo).
2. O banco novo funciona com o código antigo: as colunas extras são ignoradas. Se preferir voltar o banco também, restaure o backup feito antes de atualizar.
