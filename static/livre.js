/* Layout livre — só para o administrador.
   O painel é um quadro de 12 colunas com linhas de 1,5rem. Em "Editar layout"
   cada cartão pode ser arrastado (mover) ou puxado pelo canto (tamanho). A
   posição "encaixa" nas células, linhas verdes mostram o alinhamento com os
   outros cartões e, ao soltar o mouse, a posição é salva. Se o lugar estiver
   ocupado, o cartão volta para onde estava. */
(function () {
  var tela = document.querySelector('[data-livre]');
  if (!tela) return;
  var NCOL = 12, ALT_MIN = 4;
  var btn = document.querySelector('[data-livre-editar]');
  var ajuda = document.querySelector('[data-livre-ajuda]');
  var btnCompactar = document.querySelector('[data-livre-compactar]');
  var btnAjustar = document.querySelector('[data-livre-ajustar]');
  var editando = false, malha = null, ocupado = false;

  function cartoes() {
    return [].slice.call(tela.querySelectorAll(':scope > .cartao[data-chave]'));
  }
  function pos(c) {
    return { gx: +c.dataset.gx, gy: +c.dataset.gy, gw: +c.dataset.gw, gh: +c.dataset.gh };
  }
  function etiqueta(c) {
    var e = c.querySelector('.livre-etiqueta'), p = pos(c);
    if (e) e.textContent = p.gw + ' × ' + p.gh;
  }
  function aplica(c, p) {
    c.dataset.gx = p.gx; c.dataset.gy = p.gy; c.dataset.gw = p.gw; c.dataset.gh = p.gh;
    c.style.gridColumn = (p.gx + 1) + ' / span ' + p.gw;
    c.style.gridRow = (p.gy + 1) + ' / span ' + p.gh;
    etiqueta(c);
  }
  function metricas() {
    var cs = getComputedStyle(tela), r = tela.getBoundingClientRect();
    var gap = parseFloat(cs.columnGap) || 0, linha = parseFloat(cs.gridAutoRows) || 24;
    var cw = (r.width - gap * (NCOL - 1)) / NCOL;
    return { gap: gap, linha: linha, passo: cw + gap, cw: cw };
  }
  function bate(p, ignorar) {
    return cartoes().some(function (o) {
      if (o === ignorar) return false;
      var q = pos(o);
      return p.gx < q.gx + q.gw && q.gx < p.gx + p.gw &&
             p.gy < q.gy + q.gh && q.gy < p.gy + p.gh;
    });
  }
  function aviso(texto) {
    var a = document.createElement('div');
    a.className = 'livre-aviso'; a.textContent = texto;
    document.body.appendChild(a);
    setTimeout(function () { a.remove(); }, 2800);
  }
  function salva(lista) {
    var f = new FormData();
    f.set('csrf', tela.dataset.csrf);
    f.set('posicoes', JSON.stringify(lista));
    return fetch(tela.dataset.salvar, { method: 'POST', body: f, credentials: 'same-origin' })
      .then(function (r) {
        return r.json().catch(function () { return { ok: false, erro: 'Erro ao salvar.' }; });
      }, function () { return { ok: false, erro: 'Sem conexão com o servidor.' }; });
  }
  function item(c) {
    var p = pos(c);
    return { chave: c.dataset.chave, gx: p.gx, gy: p.gy, gw: p.gw, gh: p.gh };
  }

  /* ── fantasma e linhas-guia ── */
  var fantasma = null, linhas = [];
  function mostraFantasma(p) {
    if (!fantasma) {
      fantasma = document.createElement('div');
      fantasma.className = 'livre-fantasma';
      tela.appendChild(fantasma);
    }
    fantasma.style.gridColumn = (p.gx + 1) + ' / span ' + p.gw;
    fantasma.style.gridRow = (p.gy + 1) + ' / span ' + p.gh;
    fantasma.classList.toggle('ocupado', ocupado);
  }
  function limpaGuias() {
    if (fantasma) { fantasma.remove(); fantasma = null; }
    linhas.forEach(function (l) { l.remove(); });
    linhas = [];
  }
  function linha(tipo, px) {
    var l = document.createElement('div');
    l.className = 'livre-linha ' + tipo;
    if (tipo === 'v') l.style.left = px + 'px'; else l.style.top = px + 'px';
    tela.appendChild(l); linhas.push(l);
  }
  function guias(p, atual) {
    linhas.forEach(function (l) { l.remove(); }); linhas = [];
    var m = metricas();
    var margem = parseFloat(getComputedStyle(atual).marginBottom) || 0;
    var v = {}, h = {};
    cartoes().forEach(function (o) {
      if (o === atual) return;
      var q = pos(o);
      if (p.gx === q.gx || p.gx === q.gx + q.gw) v[p.gx * m.passo - (p.gx === q.gx ? 0 : m.gap / 2)] = 1;
      if (p.gx + p.gw === q.gx + q.gw || p.gx + p.gw === q.gx)
        v[(p.gx + p.gw) * m.passo - m.gap + (p.gx + p.gw === q.gx ? m.gap / 2 : 0)] = 1;
      if (p.gy === q.gy || p.gy === q.gy + q.gh) h[p.gy * m.linha] = 1;
      if (p.gy + p.gh === q.gy + q.gh || p.gy + p.gh === q.gy)
        h[(p.gy + p.gh) * m.linha - margem] = 1;
    });
    Object.keys(v).forEach(function (x) { linha('v', +x); });
    Object.keys(h).forEach(function (y) { linha('h', +y); });
  }

  /* ── rolagem automática enquanto arrasta ── */
  var ultimoY = 0, rolando = false;
  function rola() {
    if (!rolando) return;
    if (ultimoY > innerHeight - 60) scrollBy(0, 18);
    else if (ultimoY < 60) scrollBy(0, -18);
    requestAnimationFrame(rola);
  }

  /* ── mover e redimensionar ── */
  function arrasta(e, c, modo) {
    e.preventDefault();
    var ini = pos(c), m = metricas(), alvo = ini;
    var x0 = e.pageX, y0 = e.pageY, sy0 = scrollY;
    ultimoY = e.clientY; rolando = true; requestAnimationFrame(rola);
    if (modo === 'mover') c.classList.add('movendo');
    var zAntes = c.style.zIndex; c.style.zIndex = 1000;      // enquanto arrasta, fica por cima de tudo
    try { c.setPointerCapture(e.pointerId); } catch (_) {}

    function mover(ev) {
      ultimoY = ev.clientY;
      var dx = ev.pageX - x0, dy = ev.pageY - y0;
      if (modo === 'mover') {
        c.style.transform = 'translate(' + dx + 'px,' + dy + 'px)';
        alvo = {
          gx: Math.max(0, Math.min(NCOL - ini.gw, ini.gx + Math.round(dx / m.passo))),
          gy: Math.max(0, ini.gy + Math.round(dy / m.linha)),
          gw: ini.gw, gh: ini.gh
        };
      } else {
        alvo = {
          gx: ini.gx, gy: ini.gy,
          gw: Math.max(1, Math.min(NCOL - ini.gx, ini.gw + Math.round(dx / m.passo))),
          gh: Math.max(ALT_MIN, ini.gh + Math.round(dy / m.linha))
        };
      }
      ocupado = false;            // sobrepor é permitido; só as guias ajudam a alinhar
      mostraFantasma(alvo);
      guias(alvo, c);
    }
    function soltar() {
      rolando = false;
      c.removeEventListener('pointermove', mover);
      c.removeEventListener('pointerup', soltar);
      c.removeEventListener('pointercancel', soltar);
      c.classList.remove('movendo');
      c.style.transform = '';
      c.style.zIndex = zAntes;
      limpaGuias();
      var mudou = alvo.gx !== ini.gx || alvo.gy !== ini.gy ||
                  alvo.gw !== ini.gw || alvo.gh !== ini.gh;
      if (!mudou) return;
      aplica(c, alvo);
      c.style.zIndex = 9999;      // vai para a frente, como o servidor também grava
      salva([item(c)]).then(function (r) {
        if (!r.ok) { aplica(c, ini); c.style.zIndex = zAntes; aviso(r.erro || 'Não consegui salvar.'); }
      });
    }
    c.addEventListener('pointermove', mover);
    c.addEventListener('pointerup', soltar);
    c.addEventListener('pointercancel', soltar);
  }

  /* ── altura do conteúdo ── */
  function alturaIdeal(c) {
    var a = c.style.alignSelf, h = c.style.height, mh = c.style.minHeight;
    c.style.alignSelf = 'start'; c.style.height = 'auto'; c.style.minHeight = '0';
    var corpo = c.querySelector('.cartao-corpo'), of = corpo && corpo.style.overflow;
    if (corpo) corpo.style.overflow = 'visible';
    var px = c.offsetHeight + (parseFloat(getComputedStyle(c).marginBottom) || 0);
    if (corpo) corpo.style.overflow = of;
    c.style.alignSelf = a; c.style.height = h; c.style.minHeight = mh;
    return Math.max(ALT_MIN, Math.ceil(px / metricas().linha));
  }
  function ajustaUm(c) {
    var ini = pos(c), novo = { gx: ini.gx, gy: ini.gy, gw: ini.gw, gh: alturaIdeal(c) };
    if (novo.gh === ini.gh) return;
    aplica(c, novo);
    salva([item(c)]).then(function (r) {
      if (!r.ok) { aplica(c, ini); aviso(r.erro || 'Não consegui salvar.'); }
    });
  }
  function ajustaTodos() {
    var lista = cartoes().sort(function (a, b) {
      return (+a.dataset.gy - +b.dataset.gy) || (+a.dataset.gx - +b.dataset.gx);
    });
    var antes = lista.map(function (c) { return [c, pos(c)]; });
    var colocados = [];
    lista.forEach(function (c) {
      var p = pos(c); p.gh = alturaIdeal(c);
      function colide() {
        return colocados.some(function (q) {
          return p.gx < q.gx + q.gw && q.gx < p.gx + p.gw &&
                 p.gy < q.gy + q.gh && q.gy < p.gy + p.gh;
        });
      }
      while (colide()) p.gy++;
      colocados.push(p);
      aplica(c, p);
    });
    salva(lista.map(item)).then(function (r) {
      if (!r.ok) {
        antes.forEach(function (par) { aplica(par[0], par[1]); });
        aviso(r.erro || 'Não consegui salvar.');
      } else aviso('Cartões ajustados ao conteúdo.');
    });
  }

  // Fecha os vazios: cada cartão sobe até encostar em outro (ou no topo),
  // mantendo a coluna; o que estava sobreposto é empurrado para baixo.
  function compacta() {
    var lista = cartoes().sort(function (a, b) {
      return (+a.dataset.gy - +b.dataset.gy) || (+a.dataset.gx - +b.dataset.gx);
    });
    var antes = lista.map(function (c) { return [c, pos(c)]; });
    var colocados = [];
    lista.forEach(function (c) {
      var p = pos(c);
      function colide() {
        return colocados.some(function (q) {
          return p.gx < q.gx + q.gw && q.gx < p.gx + p.gw &&
                 p.gy < q.gy + q.gh && q.gy < p.gy + p.gh;
        });
      }
      p.gy = 0;
      while (colide()) p.gy++;
      colocados.push(p);
      aplica(c, p);
    });
    salva(lista.map(item)).then(function (r) {
      if (!r.ok) {
        antes.forEach(function (par) { aplica(par[0], par[1]); });
        aviso(r.erro || 'Não consegui salvar.');
      } else aviso('Espaços fechados.');
    });
  }

  /* ── ligar/desligar o modo de edição ── */
  function prepara(c) {
    ligaMover(c);
    if (c.querySelector('.livre-alca')) return;
    var e = document.createElement('span'); e.className = 'livre-etiqueta livre-alca-eti';
    e.style.pointerEvents = 'none';
    var a = document.createElement('span'); a.className = 'livre-alca';
    a.title = 'Arraste para mudar o tamanho; clique duas vezes para ajustar à altura do conteúdo';
    c.appendChild(e); c.appendChild(a);
    etiqueta(c);
    // O arrasto captura o ponteiro no cartão, e com isso o `dblclick` não chega
    // ao puxador; o duplo clique é reconhecido aqui, pelo intervalo entre dois.
    var ultimo = 0;
    a.addEventListener('pointerdown', function (ev) {
      if (!editando) return;
      ev.stopPropagation();
      var agora = Date.now();
      if (agora - ultimo < 400) { ultimo = 0; ev.preventDefault(); ajustaUm(c); return; }
      ultimo = agora;
      arrasta(ev, c, 'tamanho');
    });
  }
  function ligaMover(c) {
    if (c._livre) return;
    c._livre = true;
    c.addEventListener('pointerdown', function (ev) {
      if (!editando || ev.button !== 0 || ev.target.closest('.livre-alca')) return;
      seleciona(c);
      arrasta(ev, c, 'mover');
    });
  }
  /* ── excluir, copiar, recortar, colar e menu do botão direito ── */
  var FIXOS = ['sistemas', 'atalhos', 'ramais', 'noticias'];
  function nomeDe(c) {
    var h = c.querySelector('.cartao-cab h2'); return (h && h.textContent.trim()) || c.dataset.chave;
  }
  function acao(a, chave) {
    var f = new FormData(); f.set('csrf', tela.dataset.csrf); f.set('acao', a); f.set('chave', chave);
    return fetch(tela.dataset.acao, { method: 'POST', body: f, credentials: 'same-origin' })
      .then(function (r) { return r.json().catch(function () { return { ok: false, erro: 'Erro.' }; }); },
            function () { return { ok: false, erro: 'Sem conexão com o servidor.' }; });
  }
  function recarrega() {
    try { sessionStorage.setItem('livre-editando', '1'); } catch (_) {}
    location.reload();
  }
  function exclui(c) {
    var fixo = FIXOS.indexOf(c.dataset.chave) >= 0 || /^(paginas|destaque)$/.test(c.dataset.chave || '');
    if (!c.dataset.chave || /^(paginas|destaque)$/.test(c.dataset.chave)) { aviso('Este cartão da barra lateral é ligado e desligado em Navegação.'); return; }
    var msg = fixo ? 'Ocultar o cartão “' + nomeDe(c) + '”? Ele pode ser trazido de volta pelos botões da barra de edição.'
                   : 'Excluir o cartão “' + nomeDe(c) + '” e o que há nele? Isso não pode ser desfeito.';
    if (!confirm(msg)) return;
    acao('excluir', c.dataset.chave).then(function (r) {
      if (r.ok) recarrega(); else aviso(r.erro || 'Não consegui excluir.');
    });
  }
  function copia(corte) {
    if (!sel) return;
    var ch = sel.dataset.chave;
    if (FIXOS.indexOf(ch) >= 0 || /^(paginas|destaque)$/.test(ch)) { aviso('Este cartão é único: não dá para copiar ou recortar. Use Delete para ocultá-lo.'); return; }
    try { sessionStorage.setItem('livre-clip', JSON.stringify({ chave: ch, corte: !!corte })); } catch (_) {}
    sel.classList.toggle('recortado', !!corte);
    aviso(corte ? 'Recortado — use Ctrl+V para colar.' : 'Copiado — use Ctrl+V para colar.');
  }
  function cola() {
    var clip = null;
    try { clip = JSON.parse(sessionStorage.getItem('livre-clip') || 'null'); } catch (_) {}
    if (!clip) { aviso('Nada copiado ainda.'); return; }
    acao('duplicar', clip.chave).then(function (r) {
      if (!r.ok) { aviso(r.erro || 'Não consegui colar.'); return; }
      if (!clip.corte) { recarrega(); return; }
      acao('excluir', clip.chave).then(function () {
        try { sessionStorage.removeItem('livre-clip'); } catch (_) {}
        recarrega();
      });
    });
  }
  var menu = null;
  function fechaMenu() { if (menu) { menu.remove(); menu = null; } }
  function abreMenu(x, y, c) {
    fechaMenu();
    var temClip = false;
    try { temClip = !!sessionStorage.getItem('livre-clip'); } catch (_) {}
    var itens = [];
    if (c) {
      itens.push(['Copiar', 'Ctrl+C', function () { copia(false); }]);
      itens.push(['Recortar', 'Ctrl+X', function () { copia(true); }]);
    }
    itens.push(['Colar', 'Ctrl+V', cola, !temClip]);
    if (c) itens.push(['Excluir', 'Delete', function () { exclui(c); }, false, true]);
    menu = document.createElement('div'); menu.className = 'livre-menu';
    menu.style.left = Math.min(x, innerWidth - 190) + 'px'; menu.style.top = Math.min(y, innerHeight - 140) + 'px';
    itens.forEach(function (i) {
      var b = document.createElement('button'); b.type = 'button'; b.disabled = !!i[3];
      if (i[4]) b.className = 'perigo';
      b.innerHTML = '<span></span><kbd></kbd>'; b.firstChild.textContent = i[0]; b.lastChild.textContent = i[1];
      b.addEventListener('click', function () { fechaMenu(); i[2](); });
      menu.appendChild(b);
    });
    document.body.appendChild(menu);
  }
  tela.addEventListener('contextmenu', function (ev) {
    if (!editando) return;
    ev.preventDefault();
    var c = ev.target.closest('.cartao');
    if (c && c.parentNode !== tela) c = null;
    if (c) seleciona(c);
    abreMenu(ev.clientX, ev.clientY, c);
  });
  document.addEventListener('pointerdown', function (ev) { if (menu && !ev.target.closest('.livre-menu')) fechaMenu(); });
  window.addEventListener('scroll', fechaMenu, true);
  document.querySelectorAll('[data-livre-mostrar]').forEach(function (b) {
    b.addEventListener('click', function () {
      acao('mostrar', b.dataset.livreMostrar).then(function (r) { if (r.ok) recarrega(); else aviso(r.erro || 'Não consegui.'); });
    });
  });

  /* ── seleção e setas do teclado ──
     Clique num cartão para selecioná-lo; setas movem 1 passo, Shift+setas
     mudam o tamanho, Esc solta. Funciona junto com o mouse. */
  var sel = null, timerSalva = null, pendentes = {};
  function seleciona(c) {
    if (sel === c) return;
    if (sel) sel.classList.remove('selecionado');
    sel = c;
    if (sel) sel.classList.add('selecionado');
  }
  function salvaDepois(c) {
    pendentes[c.dataset.chave] = c;
    clearTimeout(timerSalva);
    timerSalva = setTimeout(function () {
      var cs = Object.keys(pendentes).map(function (k) { return pendentes[k]; });
      pendentes = {};
      cs.forEach(function (x) { x.style.zIndex = 9999; });
      salva(cs.map(item)).then(function (r) {
        if (!r.ok) aviso(r.erro || 'Não consegui salvar.');
      });
    }, 350);
  }
  document.addEventListener('keydown', function (ev) {
    if (!editando) return;
    var t = ev.target;
    if (t && /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName || '') || (t && t.isContentEditable)) return;
    if (document.querySelector('#conteudo-fundo') && document.querySelector('#conteudo-fundo').style.display === 'flex') return;
    var ctrl = ev.ctrlKey || ev.metaKey, k = ev.key.toLowerCase();
    if (ctrl && k === 'v') { ev.preventDefault(); cola(); return; }
    if (!sel) return;
    if (ctrl && k === 'c') { ev.preventDefault(); copia(false); return; }
    if (ctrl && k === 'x') { ev.preventDefault(); copia(true); return; }
    if (ev.key === 'Delete' || ev.key === 'Backspace') { ev.preventDefault(); exclui(sel); return; }
    if (ev.key === 'Escape') { seleciona(null); fechaMenu(); return; }
    var d = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[ev.key];
    if (!d) return;
    ev.preventDefault();
    var p = pos(sel);
    if (ev.shiftKey) {
      p.gw = Math.max(1, Math.min(NCOL - p.gx, p.gw + d[0]));
      p.gh = Math.max(ALT_MIN, p.gh + d[1]);
    } else {
      p.gx = Math.max(0, Math.min(NCOL - p.gw, p.gx + d[0]));
      p.gy = Math.max(0, p.gy + d[1]);
    }
    aplica(sel, p);
    sel.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    salvaDepois(sel);
  });
  document.addEventListener('pointerdown', function (ev) {
    if (!sel) return;
    if (ev.target.closest('.cartao, button, a, input, textarea, select, dialog, [role=dialog], .modal')) return;
    seleciona(null);
  });

  function liga(sim) {
    editando = sim;
    if (!sim) seleciona(null);
    tela.classList.toggle('editando', sim);
    btn.textContent = sim ? 'Concluir edição' : 'Editar layout';
    if (ajuda) ajuda.hidden = !sim;
    if (btnAjustar) btnAjustar.hidden = !sim;
    if (btnCompactar) btnCompactar.hidden = !sim;
    document.querySelectorAll('[data-livre-mostrar]').forEach(function (b) { b.hidden = !sim; });
    if (sim) {
      if (!malha) {
        malha = document.createElement('div'); malha.className = 'livre-malha';
        for (var i = 0; i < NCOL; i++) malha.appendChild(document.createElement('i'));
        tela.insertBefore(malha, tela.firstChild);
      }
      cartoes().forEach(prepara);
    } else {
      if (malha) { malha.remove(); malha = null; }
      cartoes().forEach(function (c) {
        [].forEach.call(c.querySelectorAll('.livre-alca,.livre-alca-eti'),
                        function (n) { n.remove(); });
      });
    }
  }
  // Conteúdo maior que o cartão fica cortado (sem barra de rolagem); no modo
  // de edição o cartão ganha um aviso para você aumentar a altura ou ajustar.
  function marcaCortes() {
    cartoes().forEach(function (c) {
      var k = c.querySelector('.cartao-corpo');
      var corta = editando && k && k.scrollHeight > k.clientHeight + 2;
      c.classList.toggle('corta', !!corta);
    });
  }
  var _liga = liga;
  liga = function (sim) { _liga(sim); marcaCortes(); };
  var _aplica = aplica;
  aplica = function (c, p) { _aplica(c, p); setTimeout(marcaCortes, 50); };
  // "Concluir edição" sai do editor e mostra o portal como os demais o veem.
  if (btn) btn.addEventListener('click', function () {
    if (editando) { location.href = btn.dataset.sair || '/'; } else liga(true);
  });
  // Depois de excluir/colar a página recarrega; volta direto ao modo de edição.
  try { if (sessionStorage.getItem('livre-editando')) { sessionStorage.removeItem('livre-editando'); liga(true); } } catch (_) {}
  if (btnAjustar) btnAjustar.addEventListener('click', ajustaTodos);
  if (btnCompactar) btnCompactar.addEventListener('click', compacta);
  // Evita que um clique no fim do arrasto abra o link do cartão.
  tela.addEventListener('click', function (e) {
    if (editando) { e.preventDefault(); e.stopPropagation(); }
  }, true);
})();
