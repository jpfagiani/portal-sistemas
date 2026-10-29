#!/usr/bin/env python3
"""Arruma o cartão "Assédio Moral e Sexual…" da página inicial.

O que faz (uma vez, sem apagar nada):
  1. guarda uma cópia do banco (dados.db.antes-assedio);
  2. cria a notícia "Assédio Moral e Sexual em Instituições Públicas" com o texto
     inteiro do comunicado e a imagem como capa (página com título, imagem grande e texto);
  3. troca o conteúdo do cartão por imagem + título, os dois com a mesma largura,
     e o cartão inteiro passa a levar à notícia.

Uso (na pasta do portal):   sudo python3 corrigir_assedio.py
Outro banco:                sudo python3 corrigir_assedio.py /caminho/dados.db
Depois, recarregue o portal (Ctrl+F5). Rodar de novo não faz nada (avisa que já foi ajustado).
"""
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
BANCO = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('INTRANET_DB', os.path.join(AQUI, 'dados.db'))
CHAVE = 'conteudo-a989e32e'          # cartão do Assédio
SLUG = 'assedio-moral-e-sexual'
LARGURA = 300                        # px da imagem e do título (mude aqui se quiser)

if not os.path.exists(BANCO):
    sys.exit(f'Banco não encontrado: {BANCO}')
con = sqlite3.connect(BANCO)
con.row_factory = sqlite3.Row
cartao = con.execute('SELECT p.nome, k.html FROM cartoes_painel p JOIN cartao_conteudo k ON k.chave=p.chave '
                     'WHERE p.chave=?', (CHAVE,)).fetchone()
if not cartao:
    sys.exit(f'Cartão {CHAVE} não encontrado neste banco.')
nome, html = cartao['nome'], cartao['html'] or ''

if f'href="/noticias/{SLUG}"' in html and 'class="fig' in html:
    sys.exit('Este cartão já foi ajustado antes; nada a fazer. (A cópia antiga está em dados.db.antes-assedio.)')

shutil.copy2(BANCO, BANCO + '.antes-assedio')
imagem = re.search(r'/static/uploads/([A-Za-z0-9._\-]+\.(?:png|jpe?g|gif|webp))', html)
if not imagem:
    sys.exit('Não achei a imagem dentro do cartão.')
arquivo = imagem.group(1)

# texto da notícia = o conteúdo do cartão sem o parágrafo da imagem e sem o título repetido
corpo = re.sub(r'<p[^>]*>\s*(?:<a[^>]*>)?\s*<img[^>]*>\s*(?:</a>)?\s*</p>', '', html, count=1)
corpo = re.sub(r'<p[^>]*>\s*<strong>[^<]*Reconhecer para Transformar[^<]*</strong>\s*</p>', '', corpo, count=1)
# limpa formatações que o editor foi acumulando (alinhamento forçado e tamanhos grandes demais)
corpo = re.sub(r'\s*text-align:\s*(?:justify|right|center)\s*;?', '', corpo)
corpo = re.sub(r'\s*font-size:[^;"]+;?', '', corpo)
corpo = re.sub(r'\sstyle=""', '', corpo)
corpo = re.sub(r'<span>\s*</span>', '', corpo)
corpo = corpo.replace('&nbsp;', ' ')

titulo = nome
agora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
existe = con.execute('SELECT id FROM noticias WHERE slug=?', (SLUG,)).fetchone()
colunas = {r[1] for r in con.execute('PRAGMA table_info(noticias)')}
if existe:
    con.execute("UPDATE noticias SET titulo=?, corpo=?, capa=?, estado='publicado', atualizado_em=? WHERE id=?",
                (titulo, corpo, arquivo, agora, existe['id']))
else:
    dados = {'slug': SLUG, 'titulo': titulo,
             'resumo': 'Curso EaD da CECP, de 18/09/2026 a 14/12/2026, pelo Portal de Integridade.',
             'corpo': corpo, 'capa': arquivo,
             'capa_alt': 'Banner do curso de Assédio Moral e Sexual em Instituições Públicas',
             'categoria': 'Capacitação', 'estado': 'publicado', 'publicar_em': agora}
    if 'ordem' in colunas:        # primeira posição da lista
        dados['ordem'] = con.execute('SELECT COALESCE(MIN(ordem),0)-1 FROM noticias').fetchone()[0]
    dados = {k: v for k, v in dados.items() if k in colunas}
    con.execute(f"INSERT INTO noticias ({','.join(dados)}) VALUES ({','.join('?' * len(dados))})", list(dados.values()))

destino = f'/noticias/{SLUG}'
novo = (f'<div class="fig fig-c" style="width:{LARGURA}px">'
        f'<p><a href="{destino}"><img src="/static/uploads/{arquivo}" alt="{titulo}"></a></p>'
        f'<p><a href="{destino}"><strong>{titulo}</strong></a></p></div>')
con.execute('UPDATE cartao_conteudo SET html=?, titulo_visivel=0 WHERE chave=?', (novo, CHAVE))
con.commit()
con.close()
print('Pronto. Notícia criada em', destino, '- cartão atualizado. Recarregue o portal (Ctrl+F5).')
