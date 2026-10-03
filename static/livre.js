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
      ocupado = bate(alvo, c);
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
      limpaGuias();
      var mudou = alvo.gx !== ini.gx || alvo.gy !== ini.gy ||
                  alvo.gw !== ini.gw || alvo.gh !== ini.gh;
      if (!mudou) return;
      if (bate(alvo, c)) { aviso('Esse espaço já está ocupado por outro cartão.'); return; }
      aplica(c, alvo);
      salva([item(c)]).then(function (r) {
        if (!r.ok) { aplica(c, ini); aviso(r.erro || 'Não consegui salvar.'); }
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
    if (bate(novo, c)) { aviso('Não há espaço livre embaixo para ajustar este cartão.'); return; }
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
      arrasta(ev, c, 'mover');
    });
  }
  function liga(sim) {
    editando = sim;
    tela.classList.toggle('editando', sim);
    btn.textContent = sim ? 'Concluir edição' : 'Editar layout';
    if (ajuda) ajuda.hidden = !sim;
    if (btnAjustar) btnAjustar.hidden = !sim;
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
  if (btn) btn.addEventListener('click', function () { liga(!editando); });
  if (btnAjustar) btnAjustar.addEventListener('click', ajustaTodos);
  // Evita que um clique no fim do arrasto abra o link do cartão.
  tela.addEventListener('click', function (e) {
    if (editando) { e.preventDefault(); e.stopPropagation(); }
  }, true);
})();
