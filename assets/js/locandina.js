/* Le locandine si aprono SOPRA la pagina, non in una scheda nuova.
   Il link resta un <a href> vero verso il file nel bucket: chi non ha JS, chi
   usa il click centrale o "apri in una nuova scheda" ottiene ancora l'immagine,
   e i motori vedono lo stesso markup di prima. Qui cambia solo il click
   normale, che invece di portare via da eventi.html apre un riquadro con la
   X, chiudibile anche col tasto Esc o toccando fuori dall'immagine.
   Stessa impostazione di cookie-consent.js: un file solo, che si porta dietro
   il proprio CSS, cosi' non va duplicato nei quattro generatori. */
(function () {
  'use strict';

  // Un href che finisce con un'estensione di immagine: e' quello che
  // distingue l'azione "Locandina" dalle altre .event-act ("Scheda completa",
  // "Come arrivare", "Calendario"), che devono restare link normali.
  var IMMAGINE = /\.(jpe?g|png|webp|avif|gif)(\?.*)?$/i;
  // I punti in cui il sito mostra una locandina cliccabile: le righe
  // dell'agenda e dei centri estivi, il cartellone delle pagine comune.
  var LINK = 'a.event-act, .com-poster a, a[data-locandina]';
  // Sulle schede evento la locandina non e' dentro un link: e' l'immagine
  // grande in colonna, che a 420px non si legge.
  var IMG = 'img.ev-loc';

  var CSS =
    '.daop-lb{position:fixed;inset:0;z-index:99000;display:flex;align-items:center;' +
    'justify-content:center;padding:clamp(14px,4vw,40px);background:rgba(26,45,58,.92);' +
    'font-family:"DM Sans",system-ui,sans-serif;-webkit-tap-highlight-color:transparent;' +
    'animation:daop-lb-in .18s ease-out}' +
    '.daop-lb[hidden]{display:none}' +
    '@keyframes daop-lb-in{from{opacity:0}to{opacity:1}}' +
    '@media(prefers-reduced-motion:reduce){.daop-lb{animation:none}}' +
    '.daop-lb-box{margin:0;display:flex;flex-direction:column;align-items:center;gap:10px;' +
    'max-width:100%;max-height:100%}' +
    /* 128px = spazio per la didascalia sotto e per il respiro sopra. Il dvh
       serve su iOS, dove la barra del browser mangia parte del 100vh. */
    '.daop-lb-box img{display:block;width:auto;height:auto;max-width:100%;' +
    'max-height:calc(100vh - 128px);max-height:calc(100dvh - 128px);border-radius:12px;' +
    'background:#fdf8f3;box-shadow:0 18px 50px rgba(0,0,0,.45)}' +
    '.daop-lb.is-loading .daop-lb-box img{min-width:min(60vw,220px);min-height:min(50vh,280px)}' +
    '.daop-lb-cap{margin:0;text-align:center;color:rgba(255,255,255,.86);font-size:.88rem;' +
    'line-height:1.45;max-width:min(100%,560px)}' +
    '.daop-lb-cap b{display:block;font-weight:600;color:#fff}' +
    '.daop-lb-cap a{color:#f0b070;font-weight:600;text-decoration:underline;text-underline-offset:3px}' +
    '.daop-lb-load{position:absolute;bottom:max(16px,env(safe-area-inset-bottom));' +
    'color:rgba(255,255,255,.8);font-size:.85rem;margin:0}' +
    '.daop-lb:not(.is-loading) .daop-lb-load{display:none}' +
    '.daop-lb-x{position:absolute;top:max(12px,env(safe-area-inset-top));right:12px;' +
    'width:46px;height:46px;display:flex;align-items:center;justify-content:center;' +
    'border-radius:50%;border:1px solid rgba(255,255,255,.28);background:rgba(255,255,255,.14);' +
    'color:#fff;cursor:pointer;padding:0;transition:background .2s}' +
    '.daop-lb-x:hover{background:rgba(255,255,255,.26)}' +
    'a.event-act[data-lb],.com-poster a[data-lb] img,img.ev-loc[data-lb]{cursor:zoom-in}';

  var lb = null, imgEl, capEl, titEl, origEl, chiudiBtn, tornaA = null;

  function crea() {
    if (lb) return;
    var style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    lb = document.createElement('div');
    lb.className = 'daop-lb';
    lb.hidden = true;
    lb.setAttribute('role', 'dialog');
    lb.setAttribute('aria-modal', 'true');
    lb.setAttribute('aria-label', 'Locandina');

    chiudiBtn = document.createElement('button');
    chiudiBtn.type = 'button';
    chiudiBtn.className = 'daop-lb-x';
    chiudiBtn.setAttribute('aria-label', 'Chiudi la locandina');
    chiudiBtn.innerHTML = '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">' +
      '<path d="M6 6l12 12M18 6L6 18"/></svg>';
    chiudiBtn.addEventListener('click', chiudi);

    var fig = document.createElement('figure');
    fig.className = 'daop-lb-box';
    imgEl = document.createElement('img');
    imgEl.alt = '';
    imgEl.addEventListener('load', function () { lb.classList.remove('is-loading'); });
    // Se l'immagine non arriva resta la didascalia con il link all'originale:
    // meglio di un riquadro nero senza via d'uscita.
    imgEl.addEventListener('error', function () { lb.classList.remove('is-loading'); });

    capEl = document.createElement('figcaption');
    capEl.className = 'daop-lb-cap';
    titEl = document.createElement('b');
    origEl = document.createElement('a');
    origEl.target = '_blank';
    origEl.rel = 'noopener';
    origEl.textContent = 'Apri l’immagine originale';
    capEl.appendChild(titEl);
    capEl.appendChild(origEl);

    fig.appendChild(imgEl);
    fig.appendChild(capEl);

    var caricando = document.createElement('p');
    caricando.className = 'daop-lb-load';
    caricando.textContent = 'Caricamento…';

    lb.appendChild(chiudiBtn);
    lb.appendChild(fig);
    lb.appendChild(caricando);

    // Chiude toccando fuori: il click sull'immagine o sulla didascalia non
    // deve chiudere, altrimenti chi la tocca per guardarla se la perde.
    lb.addEventListener('click', function (ev) {
      if (ev.target === lb || ev.target === fig) chiudi();
    });
    document.body.appendChild(lb);
  }

  function apri(src, quale) {
    crea();
    var titolo = (quale && quale.testo) || '';
    tornaA = document.activeElement;
    titEl.textContent = titolo;
    titEl.style.display = titolo ? '' : 'none';
    origEl.href = src;
    imgEl.alt = (quale && quale.alt) ||
                (titolo ? 'Locandina: ' + titolo : 'Locandina');
    lb.classList.add('is-loading');
    imgEl.src = src;
    if (imgEl.complete) lb.classList.remove('is-loading');
    lb.hidden = false;
    document.body.style.overflow = 'hidden';
    chiudiBtn.focus();
  }

  function chiudi() {
    if (!lb || lb.hidden) return;
    // Il fuoco non deve restare dentro un riquadro nascosto: si toglie prima
    // di chiudere, poi torna dov'era (se c'era qualcosa di focalizzabile).
    if (lb.contains(document.activeElement)) document.activeElement.blur();
    lb.hidden = true;
    // Svuota il src: se l'immagine sta ancora scaricando, chiudere ferma il
    // download invece di continuare a consumare la connessione del telefono.
    imgEl.removeAttribute('src');
    document.body.style.overflow = '';
    if (tornaA && tornaA.focus && tornaA !== document.body) tornaA.focus();
    tornaA = null;
  }

  document.addEventListener('keydown', function (ev) {
    if (!lb || lb.hidden) return;
    if (ev.key === 'Escape' || ev.key === 'Esc') { chiudi(); return; }
    // Il riquadro e' modale: con Tab il fuoco gira tra la X e il link
    // all'originale, non finisce nella pagina nascosta sotto.
    if (ev.key === 'Tab') {
      var punti = [chiudiBtn, origEl];
      var i = punti.indexOf(document.activeElement);
      var next = ev.shiftKey ? (i <= 0 ? punti.length - 1 : i - 1)
                             : (i === punti.length - 1 ? 0 : i + 1);
      punti[next].focus();
      ev.preventDefault();
    }
  });

  // La didascalia dice DI CHE COSA e' la locandina: dal titolo della riga
  // nell'agenda, dall'alt dell'immagine dove il titolo non c'e' (cartellone
  // del comune, schede evento). Se l'alt gia' dice "Locandina di ...", vale
  // anche come alt del riquadro senza ripetere la parola due volte.
  function titoloDi(el) {
    var card = el.closest('.event-card');
    var nome = card && card.querySelector('.ev-name');
    if (nome) return { testo: nome.textContent.trim(), alt: '' };
    var fig = el.closest('figure');
    var dentro = el.querySelector && el.querySelector('img');
    var im = dentro || (fig && fig.querySelector('img'));
    var alt = (im && im.getAttribute('alt')) || '';
    return { testo: alt, alt: alt };
  }

  document.addEventListener('click', function (ev) {
    // Ctrl/cmd-click, shift-click e click col rotellino restano quelli del
    // browser: chi vuole la scheda nuova la ottiene ancora.
    if (ev.defaultPrevented || ev.button !== 0 ||
        ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
    var t = ev.target;
    if (!t || !t.closest) return;

    var a = t.closest(LINK);
    if (a && IMMAGINE.test(a.getAttribute('href') || '')) {
      ev.preventDefault();
      apri(a.href, titoloDi(a));
      return;
    }
    var im = t.closest(IMG);
    if (im && im.getAttribute('src')) {
      ev.preventDefault();
      var alt = im.getAttribute('alt') || '';
      apri(im.src, { testo: alt, alt: alt });
    }
  });

  // Marca gli elementi che diventano cliccabili, solo per il cursore a lente:
  // se questo file non parte, nessuno promette uno zoom che non c'e'.
  function segna() {
    var i, n = document.querySelectorAll(LINK);
    for (i = 0; i < n.length; i++) {
      if (IMMAGINE.test(n[i].getAttribute('href') || '')) n[i].setAttribute('data-lb', '');
    }
    n = document.querySelectorAll(IMG);
    for (i = 0; i < n.length; i++) n[i].setAttribute('data-lb', '');
    // Il CSS del cursore vive dentro il riquadro: va creato comunque.
    crea();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', segna);
  } else {
    segna();
  }
})();
