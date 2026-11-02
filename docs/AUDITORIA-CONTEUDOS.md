# Consolidação de Conteúdos — relatório (versão 1.9.29)

Objetivo do roteiro: **Administração → Conteúdos → Editor unificado** como único caminho para editar notícias, cartões e comunicados.

## Auditoria (fase 1) e ação tomada

| Componente antigo | Onde era usado | Ainda necessário? | Ação |
|---|---|---|---|
| Rota `/admin/noticias` (POST: salvar, publicar, excluir) | Formulário antigo `admin_noticias.html` | Não | **Só redireciona** (GET). POST removido |
| `admin_noticias.html` | Só a rota acima | Não | **Removido** |
| `static/noticia-ordem.js` | Só `admin_noticias.html` | Não | **Removido** (ordenar usa `ordenar.js`) |
| Rota `/admin/noticia-rapida` | Nenhum JS a chamava mais | Não | **Removida** |
| Rota `/admin/lateral` (POST: salvar item, excluir, novo/excluir cartão, nome, aparência) | Links antigos, lista.html, blocos.html | Não | **Só redireciona** (GET). POST removido |
| Rota `/admin/cartao-conteudo` (POST) | Só `cartao-edicao.js` e testes | Não | **Removida** |
| `static/cartao-edicao.js` | Nenhum template | Não | **Removido** |
| `static/alinha-texto.js`, `barra-extra.js`, `editor-estado.js` | Nenhum template | Não | **Removidos** |
| `static/noticia-edicao.js` | `modulo.html` (janela de edição de *página do menu*, não de notícia) | Sim, é exclusivo | **Mantido**; comentário corrigido |
| `/admin/imagem-tamanho/<id>` | Alças de arrastar em comunicados antigos | Sim, para itens ainda no formato antigo | **Mantido** |
| `/admin/cartao-acao`, `/admin/cartao-pos` | Editor visual de layout (Editar portal) | Sim, é layout, não conteúdo | **Mantidos** |

## Rotas redirecionadas

- `/admin/noticias`, `/admin/noticias?editar=ID`, `?nova=1` → Conteúdos (lista ou editor único)
- `/admin/lateral`, `?cartao=`, `?editar=`, `?novo=1` → Conteúdos / editor único
- `/admin/cartoes` → Conteúdos

## Caminho único de gravação

`/admin/conteudos/salvar` (tipo `noticia`, `cartao`, `comunicado`), `/admin/conteudos/excluir`, `/duplicar`, `/previa`, `/ordenar`, `/criar-pagina`.

## Links migrados

Cabeçalho do cartão "Últimas notícias" (modo edição), cabeçalho dos cartões de comunicados, página "lista" dos cartões, painel inicial do admin, Biblioteca de mídia (onde cada imagem é usada), atalhos "Editar notícias/itens".

## Funcionalidades migradas ou criadas

- Comunicados no editor rico (campo `lateral.corpo_html`), com conversão automática dos antigos.
- Botão único **+ Novo conteúdo** (notícia, cartão ou comunicado).
- Editor mostra o **tipo** do conteúdo no topo.
- Página interna para cartões/comunicados (notícia de apoio, fora das listas).

## Decisões / pendências

- A seção **Cartões da página inicial** (nome, aparência) ficou dentro de Conteúdos, por pedido anterior do administrador; o roteiro sugeria uma tela de Configurações → Layout. Ficou como está.
- Campos específicos da notícia aparecem no mesmo editor, mas ainda não dentro de um bloco recolhível "Campos da notícia".
- Sistemas, Atalhos e Ramais continuam com cadastro próprio (são listas de botões/telefones, não conteúdo editorial).
- Os comunicados antigos (sem `corpo_html`) continuam aparecendo como antes até serem salvos no editor novo.
