# Mapa de destinos do clique (Fase 1)

Evidência de código para cada item que vira link na página inicial. Valores "se vazio" e "abre em" são os de hoje.

| Tipo | Onde se edita | Campo | Se vazio | Onde o clique é construído | Abre em |
|---|---|---|---|---|---|
| Notícia | Conteúdos → Notícia | `noticias.destino_url` | abre `/noticias/<slug>` | `templates/index.html` (`a.not-item`, `a.not-chamada`) | nova aba só se começa com http |
| Cartão de texto e imagem | Conteúdos → Cartão | `cartao_conteudo.url` | sem link | `templates/index.html` (`a.cartao-overlay`) | nova aba só se http |
| Comunicado | Conteúdos → Comunicado | `lateral.url` + `lateral.url_rot` | sem link | `templates/blocos.html` (imagem, botão "Abrir", `com-overlay`) | sempre nova aba |
| Sistema | Sistemas e atalhos | `links.url` | ladrilho sem link | `templates/blocos.html` (`a.ladrilho`) | sempre nova aba |
| Atalho | Sistemas e atalhos | `links.url` | sem link | `templates/blocos.html` (`a.atalho`) | sempre nova aba |
| Banner | Banner | `banners.url` | sem link | `templates/index.html` (`a.slide-link`) | sempre nova aba |
| Bloco de página | Páginas do menu | `pagina_blocos.url` | sem link | `app.py` (`agrupar_blocos`) | conforme o endereço |
| Link no texto | Editor de texto | `<a href>` | — | `app.py` (`limpa_html`) | nova aba se externo |
| Ramais | Ramais | — | — | só o título do cartão leva à lista | mesma aba |

## Lacunas em relação à especificação
1. Seis campos de destino em seis tabelas, sem regra única; só notícia, cartão de texto e comunicado têm a lista de páginas.
2. Link interno abre em nova aba em comunicados, sistemas, atalhos e banners.
3. `endereco_seguro` assume `http://` quando falta esquema (`ramais` vira `http://ramais`).
4. Destino quebrado (notícia excluída) não é detectado; o visitante vê 404.
5. Imagem do cartão e capa são a mesma coluna (`noticias.capa`).
6. Blocos de página: texto, imagem, subtítulo e botão; sem colunas, citação ou separador.
