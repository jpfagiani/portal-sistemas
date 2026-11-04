# Modernização do portal — registro das fases

Este arquivo registra o que foi feito seguindo a Especificação-Mestra do Portal Editorial
(versão 1.9.16 → 1.10.0). Tudo foi feito numa cópia de desenvolvimento; nada foi implantado.

## Fase 0 — Inventário (resumo)

- Flask + Jinja + SQLite (`dados.db`), 19 tabelas, 38 rotas (+1 nova), gunicorn com 3 processos.
- `app.py` concentra as rotas e a limpeza de HTML; `modulos/` guarda notícias, mídia, cartões,
  auditoria e segurança.
- Segurança existente: login com limite de tentativas, todas as rotas `/admin` com
  `@admin_obrigatorio`, CSRF em todo POST, lista de elementos permitidos no HTML (`limpa_html`),
  upload conferido pelo conteúdo real, `secret.key` criada uma única vez com permissão 600.
- Arquivos soltos na raiz (`index.html`, `blocos.html`, `style.css`, `encaixe.js`) parecem cópias
  antigas de `templates/` e `static/`. **Não foram apagados**: precisam de confirmação.

## Fase 1 — Linha de base

| Comando | Resultado antes das mudanças |
|---|---|
| `python3 -m py_compile app.py modulos/*.py` | passou |
| `python3 -I tests/verificacoes_portal.py` | 129 verificações, todas passaram |
| `python3 -m unittest discover -s tests -v` | não achava nenhum teste (script comum) |

## Entregas desta versão

| Fase | O que mudou |
|---|---|
| Backup | `portal-backup-*.zip` saiu do repositório; `.gitignore` agora o ignora. |
| 2–3 | Coluna de leitura de 640px como no UOL (imagem na largura da coluna e texto abaixo, nas mesmas bordas), texto de 20px/32px; resumo em tópicos nas manchetes e listas; tokens de espaçamento e raio. |
| 4 | Editor de notícias: salva por fetch (o texto nunca se perde se der erro), selo de estado (sem alterações, pendente, salvando, salvo, falha), aviso ao sair com alterações, erro junto do campo, prévia fiel à página pública (rota `/admin/noticias/previa`, mesmo template, nada gravado). |
| 5 | Biblioteca de mídia: imagens usadas na coluna lateral, no texto das páginas e nos cartões agora contam como "em uso" (antes podiam ser excluídas por engano); dimensões em pixels na listagem. |
| 6 | Cabeçalho `Content-Security-Policy` (desligável com `PORTAL_CSP=0`); testes novos; `unittest discover` funciona. |
| 7 | Sem rolagem horizontal nas telas de administração no celular; contraste e rótulos corrigidos (sem violações WCAG A/AA automáticas nas páginas testadas); testes de backup e restauração. |

## Arquivos alterados

`app.py` (versão, cores padrão), `modulos/noticias.py` (respostas JSON, prévia), `modulos/midia.py`
(usos, dimensões), `modulos/seguranca.py` (CSP), `templates/noticias.html`, `noticia.html`,
`admin_noticias.html`, `admin_midia.html`, `static/limpo.css`, `static/style.css`,
`static/editor-estado.js` (novo), `tests/verificacoes_portal.py`, `tests/test_unittest.py` (novo),
`.gitignore`, `docs/MODERNIZACAO.md` (novo).

Nenhuma tabela, coluna ou arquivo de dados foi alterado: **não há migração de banco nesta versão**.

## Testes executados

- `python3 -I tests/verificacoes_portal.py`: 153 verificações, todas passaram (inclui salvar por fetch,
  prévia, CSRF, uso de imagem, CSP, backup e restauração, entrada `../` em backup).
- `python3 -m unittest discover -s tests -v`: passa.
- Navegador real (Chromium): editor completo (estado, erro, falha do servidor, prévia, aviso de
  saída), páginas públicas e de administração em 390, 768 e 1366px; axe-core WCAG A/AA.
- Não executado: teste em celular físico, leitor de tela, Firefox/Safari, carga e desempenho,
  restauração de backup em outra máquina.

## Riscos conhecidos e decisões pendentes

1. **Backup no GitHub.** Se `portal-backup-2026-10-23-1625.zip` já foi enviado ao repositório, ele
   continua no histórico (traz usuários, hashes de senha e uploads). Remover do histórico é decisão
   do responsável: `git rm --cached portal-backup-*.zip`, commit e, para limpar o histórico,
   `git filter-repo`. Considere trocar as senhas dos usuários daquele backup.
2. **CSP com `unsafe-inline`.** O portal usa scripts e estilos escritos dentro das páginas. A
   política limita a origem do que carrega, mas não impede script escrito na própria página; quem
   impede isso é a limpeza do HTML no servidor. Remover o `unsafe-inline` exige mover esses
   scripts para arquivos (trabalho futuro).
3. **Cores já gravadas.** Os padrões novos de cor de texto secundário (`#5b6b82`) só valem para
   instalações novas e cartões novos. Quem já personalizou em Administração → Aparência mantém o
   valor antigo (`#7c8ba1`, contraste 3,5:1); trocar a cor lá resolve.
4. **Capa enviada agora não aparece na prévia** até salvar (a prévia não grava arquivos).
5. **Notícias antigas** só ganham as caixas "figura" (texto exatamente na largura da imagem)
   depois de abertas no editor e salvas uma vez; o alinhamento em tempo real continua cobrindo as demais.
6. **Arquivos soltos na raiz** (ver Fase 0): confirmar se podem ser removidos.

## Decisão sobre o editor rico (seção 10 da especificação)

**Mantido o editor atual** nesta versão. Motivos: o conteúdo já gravado usa classes próprias
(`im-c`, `figura`, colunas) que um editor novo teria de reproduzir; o TipTap exigiria etapa de
build (Node) que o portal, instalado por `instalar.sh` no Debian, não tem hoje; e a licença de
cada extensão precisa ser conferida. Nada foi adicionado como dependência. Próximo passo
recomendado, se houver interesse: prova de conceito isolada com amostras reais de notícias
(exportar `noticias.corpo` do banco) e comparação da renderização antes e depois.

## Instalação e verificação

1. Faça um backup em Administração → Backup e guarde o `.zip` fora da pasta do portal.
2. Copie a pasta do portal (ou confirme que o `git status` está limpo).
3. Extraia `portal-atualizacao.zip` sobre a pasta do portal.
4. `sudo systemctl restart portal` (ou `./atualizar.sh`) e Ctrl+F5 no navegador.
5. Abra Administração → Notícias, edite uma notícia, clique em **Prévia** e depois em **Salvar**.
6. Para validar: `python3 -I tests/verificacoes_portal.py` (usa cópia temporária; não toca no banco real).

## Reversão

Não há alteração de banco. Para voltar à versão anterior, restaure os arquivos listados acima a
partir da cópia feita no passo 2 (ou `git checkout -- <arquivos>`), apague `static/editor-estado.js`,
`tests/test_unittest.py` e `docs/MODERNIZACAO.md` e reinicie o serviço. Para desligar só a política
de segurança de conteúdo sem mexer em arquivos: defina `PORTAL_CSP=0` no serviço e reinicie.

## Próximas fases sugeridas

- Mesma prévia, estado de salvamento e aviso de saída para a edição "na própria página" e para os
  editores de páginas e cartões (hoje só o editor completo de notícias os tem).
- Componentes de cartão e manchete compartilhados entre a página inicial e a lista de notícias.
- Mover scripts embutidos para arquivos e remover `unsafe-inline` da CSP.
- Prova de conceito do TipTap com conteúdo real.
- Teste em aparelhos e leitor de tela; Firefox e Safari.

## 1.10.1 — texto colado e conteúdo antigo na notícia

Na página pública da notícia, toda imagem (pequena, média, grande, com largura em px, flutuante ou dentro
de caixa "figura") passa a ocupar a coluna inteira, e todo texto fica na mesma largura, alinhado à
esquerda, mesmo que tenha sido colado centralizado. Vale para notícias novas e antigas, sem precisar
salvar de novo. Blocos de colunas (`.cols`) continuam livres. Reversão: apagar o último bloco de
`static/limpo.css` ("Notícia no padrão do UOL").

## 1.9.22 — Cartões dentro de Conteúdos (Fases 0 e 1 do plano de 29/10/2026)

- **Aba "Cartões do painel" removida.** Em Administração → Conteúdos há agora a seção
  "Cartões da página inicial" (nome, ícone de cada cartão, fonte e cores, vitrine de notícias, novo cartão de
  comunicados, excluir cartão) e o filtro "Comunicados → cartão", com ordem por arrastar e caixa de visível.
  `/admin/lateral` e `/admin/cartoes` continuam existindo e redirecionam para Conteúdos; o POST de ordenar e excluir
  itens segue em `/admin/lateral`. Os templates `admin_lateral.html` e `admin_cartoes.html` foram removidos.
- **Erro 405 corrigido:** o formulário de aparência de "Últimas notícias" na tela Conteúdos agora é aceito
  (`/admin/conteudos` passou a receber POST).
- **Testes:** `tests/test_modulos.py` virou `tests/verificacoes_portal.py` (o `unittest discover` tentava importá-lo e
  quebrava). 225 verificações passam; `python3 -m unittest discover -s tests` passa.
- **Texto exatamente na largura da imagem, em qualquer cartão ou conteúdo** (`agrupa_figuras` em `app.py`), tamanho da
  letra e da imagem em pixels (`static/tamanho-px.js`, `static/editor-rico.js`), grade de notícias opcional.
- **Não alterado:** banco de dados (sem migração), `secret.key`, uploads. Cópias antigas na raiz (`index.html`,
  `blocos.html`, `style.css`, `encaixe.js`) e os scripts sem uso (`static/barra-extra.js`, `static/alinha-texto.js`)
  aguardam sua confirmação para serem removidos.
- Reversão: restaurar os arquivos anteriores; não há alteração de banco.

Mapa de destinos (Fase 1): ver `docs/MAPA-DE-DESTINOS.md`.

## 1.9.23 — Nomes dos cartões ocultos no portal
- O nome do cartão (conteúdo) serve só para o administrador gerenciar; no portal público não aparece mais por padrão.
- Cartões novos nascem com "Mostrar o nome do cartão" desmarcado. Para ter título, escreva-o dentro do conteúdo.
- Migração única (`titulos_ocultos_v1`) esconde o nome dos cartões já existentes. Em modo de edição o admin continua vendo o nome.

## 1.9.24 — Nome oculto também nos cartões de comunicados
- Cartões do tipo comunicados ("itens") também não mostram o nome no portal por padrão (config `<cartao>_titulo_visivel`).
- Em Conteúdos → Cartões da página inicial, a caixa "Mostrar o nome no portal" liga/desliga por cartão (comunicados e texto/imagem).

## 1.9.25 — Um só editor: comunicados também usam o editor rico
- Comunicados agora são editados no mesmo editor de texto e imagens dos cartões e notícias (fonte, tamanho em px, cor, alinhamento, imagem com texto embaixo, links). Nova coluna `lateral.corpo_html`.
- O campo "Nome" do comunicado serve só para gerenciar; não aparece no portal. Escreva o título dentro do texto.
- Comunicados antigos (título + texto + imagem) abrem já convertidos: imagem, título em negrito e texto; ao salvar passam ao formato novo.
- Urgência (selo), destaque, visível e endereço continuam como opções do item.

## 1.9.26 — Página interna para qualquer cartão
- Botão "Criar página interna deste cartão" (cartões de texto/imagem e comunicados): cria uma página como uma notícia com o conteúdo salvo, liga o clique do cartão a ela e abre a edição.
- Nova coluna `noticias.so_pagina`: páginas de apoio não aparecem em "Últimas notícias", na vitrine nem na lista de notícias; só pelo link. Caixa "Página de apoio" no editor de notícia.

## 1.9.27 — Destino escolhível em Sistemas, Atalhos e Banners
- Os campos de endereço de Sistemas/Atalhos e Banners passam a oferecer a lista de páginas e notícias do portal, além de aceitar um site (https://...).

## 1.9.28 — Criar página interna deixa só a chamada no cartão
- Ao criar a página interna, o texto completo vai para a página; o cartão fica com as imagens e uma linha de chamada (o nome), editável.

## 1.9.29 — Consolidação (roteiro): um só caminho de edição
Veja `docs/AUDITORIA-CONTEUDOS.md`. Rotas antigas `/admin/noticias` e `/admin/lateral` só redirecionam; removidos `/admin/noticia-rapida`, `/admin/cartao-conteudo`, `admin_noticias.html` e 5 JS sem uso; botão único "+ Novo conteúdo"; ordenar em `/admin/conteudos/ordenar`.

## 1.9.30 — "Deixar só imagem e chamada no cartão"
- Para cartões/comunicados que já têm página interna: o botão troca o texto do cartão por uma linha de chamada (perguntada na hora); o texto completo fica só na página.

## 1.9.31 — Chamada e matéria independentes (roteiro "Editor de notícias com referências visuais")
- Notícia: bloco 1 (chamada da página principal: título, resumo, imagem exclusiva, legenda, alt, formato, destino) e bloco 2 (matéria completa: título, subtítulo, capa, corpo); bloco 3 organização (categoria, situação, agendamento, visibilidade da chamada, destaque). Salvar um bloco não altera o outro.
- Formatos da chamada: padrão do cartão, manchete, cartão, faixa, somente texto; modelo do cartão também "agrupado por categoria".
- Prévia isolada da chamada, da página principal e da matéria, com visão de computador/tablet/celular.
- Cartões e comunicados: chamada (o que aparece no cartão) + matéria completa própria em `/materia/cartao/<chave>` e `/materia/comunicado/<id>`; o clique leva à matéria. Os botões "Criar página interna" e "Deixar só chamada" (que criavam uma notícia oculta) foram substituídos por isso.
- Detalhes em `docs/PLANO-DE-REVERSAO.md`.

## 1.9.32 — Cartões existentes passam ao novo formato
- Migração única (`materia_migrada_v1`): cartões e comunicados que apontavam para uma página de apoio (notícia oculta) recebem o texto dela como matéria completa e ficam só com imagens e uma linha de chamada; o link antigo é limpo (o clique vai à matéria).
- Botão "Mover o texto deste cartão para a matéria completa" no bloco 2 de cartões e comunicados: leva o texto atual para a matéria e deixa no cartão a imagem e uma chamada.

## 1.9.33 — Editor de notícia em painéis (roteiro "Editor de notícias com referências visuais")
- Novo layout do editor de notícias, como nas referências: cabeçalho com trilha (Conteúdos › Notícias › Editar) e botões Pré-visualizar / Salvar rascunho / Publicar; painel 1 (chamada: título e resumo com contador, imagem com Trocar/Enviar/Remover, legenda, crédito, texto alternativo, formato, destino do clique, prévia da chamada); painel 2 (matéria: título, subtítulo, capa com Trocar/Remover/Ver imagem, legenda, crédito, alt, corpo no editor rico existente, contador de caracteres); painel 3 (organização: categoria, posição na página, ordem, exibir na página principal, destaque, situação, agendamento); painel 4 (visualização com abas Página principal / Matéria completa / Mobile e aparelhos computador/tablet/celular); barra de estado (sem alterações, não salvas, salvando, salvo às HH:MM, erro) com último publicado e histórico.
- Destino do clique: página da notícia (padrão), outra página do portal ou endereço externo.
- Prévia ao vivo (a cada pausa na digitação), sem gravar nada; falha de salvamento mantém o que foi digitado.
- Banco (somente aditivo): `noticias.chamada_credito`, `noticias.capa_credito`, `noticias.chamada_posicao` ('' automática | principal | lista). A ordem usa a coluna `ordem` existente (campo "Ordem" = posição 1..N).
- Arquivos novos: `templates/admin_noticia_painel.html`, `static/noticia-painel.js`. Alterados: `admin_conteudo_editor.html`, `admin_conteudo_previa.html`, `noticia.html`, `chamada.html`, `modulos/conteudos.py`, `modulos/noticias.py`, `app.py`, `static/limpo.css`, `tests/verificacoes_portal.py`.
- Reversão: restaurar esses arquivos e apagar os dois novos. As colunas novas são ignoradas pelo código antigo.
- Não alterados: `secret.key`, uploads, registros, slugs. Cartões e comunicados continuam no editor anterior.
- **Cartões e comunicados no mesmo layout:** `templates/admin_cartao_painel.html` (novo) usa os mesmos quatro painéis: 1 chamada (nome interno, texto e imagens no editor rico, destino do clique, prévia), 2 conteúdo completo (título e texto da matéria, botão "Mover o texto deste cartão para a matéria completa"), 3 organização (comunicado: exibir, urgência, destaque; cartão: atalhos para posicionar) e 4 visualização (Chamada / Matéria completa / Mobile). Mesmo script (`static/noticia-painel.js`), sem mudança de banco e sem mudança na gravação: chamada e matéria continuam independentes.

## 1.9.34 — Padrão visual da página principal
- Imagens das chamadas em 4:3 (grade, cartão, manchete, faixa); imagens de cartões e comunicados em quadro 4:3 sem cortar.
- 1.9.34b: padrão também nas imagens de tamanho livre, ao lado do texto e dentro do texto de cartões e comunicados; título e texto de comunicados seguem o padrão (só o tamanho escolhido no próprio item prevalece, não o de Aparência).
- Títulos 19px negrito, entrelinha 27px; texto de apoio 14px/20px; 12px entre imagem e título.
- Variáveis `--pad-*` no fim de `static/limpo.css`: para mudar o padrão, altere só ali. Tamanho de título escolhido por notícia continua valendo.
- Vitrine: no máximo `--col` colunas, nunca com menos de 150px. "Últimas notícias" em lista não mudou.
- Reversão: apagar o bloco "Padrão visual" no fim de `limpo.css`.

## 1.9.35 — Tudo igual na página principal
- Todas as imagens (chamadas, cartões, comunicados, ao lado ou dentro do texto) em 225×168 px; todo texto em 14px negrito, entrelinha 20px. Valores em `--pad-*` no fim de `static/limpo.css`.
- Só o tamanho escolhido dentro de um comunicado específico prevalece. Miniaturas da lista "Últimas notícias" mantidas pequenas.
- Reversão: apagar o bloco "1.9.35" do fim de `limpo.css`.

## 1.9.36 — Redimensionar imagens arrastando qualquer lado
- Nova biblioteca `static/redimensiona.js` (8 alças: 4 lados + 4 cantos; cantos mantêm a proporção, lados são livres, Shift mantém a proporção; duplo clique volta ao padrão).
- Editor de texto (`editor-rico.js`): imagens de cartões, comunicados, matérias e notícias; tamanho gravado em px (largura e altura) no próprio HTML (o filtro `limpa_html` aceita `data-py`/`height:px`).
- Imagem da chamada e capa da notícia: colunas novas `noticias.chamada_pw/chamada_ph/capa_pw/capa_ph` (0 = padrão). Imagem de comunicado na página principal (modo de edição): `lateral.img_pw/img_ph`, gravado ao soltar.
- Padrão 225×168 continua valendo para imagens sem tamanho escolhido.
- Fora desta versão: banner e blocos de imagem das páginas internas.
- Reversão: colunas novas são ignoradas pelo código antigo.

## 1.9.37 — Imagem e texto alinhados; espaçamento escolhido no editor
- Imagem e texto começam na mesma margem esquerda (sem faixa de fundo ao lado da imagem).
- Barra do editor: grupo "Espaço" (acima − +, abaixo − +, linhas − +, Juntar, Normal) em `static/espacamento.js`; vale para os parágrafos selecionados e, com imagem selecionada, para a imagem e o texto logo abaixo.
- `limpa_html` aceita `margin-top`/`margin-bottom` (−24 a 80 px) e `line-height` (10 a 80 px).
- Reversão: remover `espacamento.js` e as linhas que o carregam; o HTML salvo continua válido.

## 1.9.38 — Imagens e textos abaixo delas iguais
- Imagem 225×168 preenche o quadro (cover): sem faixa vazia embaixo, a distância ao texto é sempre a mesma (6 px).
- Texto abaixo da imagem sempre à esquerda (mesmo em conteúdos antigos centralizados), 14px negrito, cor padrão do texto (cor escolhida no editor continua valendo).
- Nova imagem entra alinhada à esquerda (antes centralizada).
- Botão "Proporção original" na barra da imagem: mostra a imagem inteira, sem recorte.

## 1.9.39 — Alinhamento do editor vale na prévia e na página
- Corrigido: a 1.9.38 forçava imagem e texto à esquerda. Agora esquerda, centro e direita escolhidos no editor valem na prévia da chamada, na prévia da página e no portal (imagem e texto abaixo dela).

## 1.9.40 — Conferir destinos: uma matéria, uma página
- Nova tela `Conteúdos → Conferir destinos` (`/admin/conteudos/destinos`): lista cada cartão e comunicado, aonde o clique leva (site, página do portal, matéria própria, sem link, quebrado) e acha notícias com o mesmo título, título parecido ou a mesma imagem.
- Botão "Levar a esta notícia" (`/admin/conteudos/unificar`): o clique passa a abrir a página da notícia. A matéria própria não é apagada; "Usar matéria própria" desfaz.
- Página `/materia/...` sem título digitado usa o primeiro título/negrito do texto (nunca o nome administrativo).
- Reversão: remover a rota e o template; nada no banco foi alterado (só o campo `url` do item quando o administrador clica no botão).

## 1.9.41 — Corrigir o destino na própria tela "Conferir destinos"
- Cada linha tem o campo de destino (lista de páginas e notícias ou endereço http/https) com "Salvar destino", mais "Editar matéria" (cartão/comunicado) e "Editar notícia". Destino inválido é recusado com mensagem; campo vazio volta a abrir a matéria própria.

## 1.9.42 — Padrão de cores dos textos
- Notícias (lista "Últimas notícias" e chamadas sem foto): título em azul (#2563eb; azul claro no tema escuro), negrito.
- Texto abaixo de imagem (cartões, comunicados e chamadas com foto): preto, negrito 14px. Cor escolhida dentro do texto no editor continua valendo.
- A cor própria por notícia (`--n-cor`) não vale mais na lista: a cor é a do padrão.
- Inclui tudo da 1.9.41 (a 1.9.40 enviada não tinha a edição do destino em "Conferir destinos").
- Reversão: remover o bloco "Padrão de cores 1.9.42" no fim de `static/limpo.css`.
