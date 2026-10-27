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
| `python3 -I tests/test_modulos.py` | 129 verificações, todas passaram |
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
`static/editor-estado.js` (novo), `tests/test_modulos.py`, `tests/test_unittest.py` (novo),
`.gitignore`, `docs/MODERNIZACAO.md` (novo).

Nenhuma tabela, coluna ou arquivo de dados foi alterado: **não há migração de banco nesta versão**.

## Testes executados

- `python3 -I tests/test_modulos.py`: 153 verificações, todas passaram (inclui salvar por fetch,
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
6. Para validar: `python3 -I tests/test_modulos.py` (usa cópia temporária; não toca no banco real).

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
