"""Recursos do portal organizados em módulos.

O `app.py` continua sendo o ponto de entrada e guarda o núcleo (banco, login,
páginas existentes). Os recursos novos moram aqui, cada um com as suas tabelas,
rotas e regras — nada de depender de um arquivo único cada vez maior:

  seguranca  limite de tentativas de login, cabeçalhos, páginas de erro,
             conferência do conteúdo real dos arquivos enviados
  auditoria  histórico de alterações feitas na administração
  midia      biblioteca de imagens
  noticias   notícias e publicações, com rascunho e agendamento
  cartoes    cartões livres de texto e imagem, criados na própria página
  conteudos  aba única e editor único para cartões, notícias e comunicados

Cada módulo importa o núcleo (`import app as nucleo`) e se registra nele. O
núcleo carrega este pacote depois de definir tudo o que os módulos usam.
"""
from . import seguranca, auditoria, midia, noticias, cartoes, conteudos   # noqa: F401  (registram rotas)

SCHEMA = seguranca.SCHEMA + auditoria.SCHEMA + midia.SCHEMA + noticias.SCHEMA + cartoes.SCHEMA
