/* DAOP - tracciamento dei clic che GA4 da solo non vede.
 *
 * Perche' esiste come file esterno e non come blocco inline: il blocco inline
 * vive nelle 11 pagine scritte a mano, e sulle ~260 pagine generate ricopiarlo
 * avrebbe voluto dire 2 KB in piu' su ognuna e undici copie da tenere
 * allineate. Cosi' e' una richiesta sola, in cache dalla seconda pagina in poi.
 *
 * Cosa NON serve tracciare qui: la navigazione interna. Ogni pagina del sito
 * manda gia' un page_view (lo carica cookie-consent.js dopo il consenso),
 * quindi "da questa scheda dove vanno dopo" si legge gia' in GA4 con
 * un'esplorazione di percorso. Qui stanno solo i clic che NON producono un
 * page_view: quelli che portano fuori dal sito o che aprono un'app.
 *
 * I nomi degli eventi sono gli stessi del blocco inline, di proposito: la
 * serie storica di eventi.html e della home non si spezza.
 *
 * gtag esiste solo dopo il consenso ai cookie: ogni chiamata e' protetta, e
 * senza consenso lo script gira a vuoto senza errori.
 */
(function () {
  function track(nome, href) {
    if (typeof gtag === 'function') { gtag('event', nome, { link_url: href }); }
  }

  function nome_evento(href) {
    if (href.indexOf('mailto:') === 0) return 'click_email';
    if (href.indexOf('tel:') === 0) return 'click_telefono';
    if (href.indexOf('ginettoapp.it') !== -1) return 'apri_ginetto';
    if (href.indexOf('gioco.sane-italia.it') !== -1) return 'gioca_ora';
    if (href.indexOf('instagram.com') !== -1 || href.indexOf('facebook.com') !== -1) return 'click_social';
    // I tre sotto sono nuovi e valgono solo sulle pagine evento: dicono se la
    // scheda ha fatto il suo mestiere. Chi apre la mappa o si segna la data sul
    // calendario ci sta andando davvero, ed e' un segnale piu' forte di
    // qualunque tempo sulla pagina.
    if (href.indexOf('google.com/maps') !== -1) return 'apri_mappa';
    if (href.indexOf('calendar.google.com') !== -1) return 'aggiungi_calendario';
    if (href.indexOf('/storage/v1/object/public/locandine/') !== -1) return 'apri_locandina';
    return null;
  }

  function avvia() {
    document.querySelectorAll('a[href]').forEach(function (a) {
      var href = a.getAttribute('href') || '';
      var nome = nome_evento(href);
      if (!nome) return;
      a.addEventListener('click', function () { track(nome, href); });
    });

    // Profondita' di scroll: evento a 25/50/75/100%. Su una scheda evento dice
    // se sono arrivati in fondo, dove stanno la firma e i link alle landing.
    var soglie = [25, 50, 75, 100], raggiunte = {};
    window.addEventListener('scroll', function () {
      var h = document.documentElement;
      var scrollabile = h.scrollHeight - h.clientHeight;
      if (scrollabile <= 0) return;
      var perc = (h.scrollTop || document.body.scrollTop) / scrollabile * 100;
      soglie.forEach(function (s) {
        if (perc >= s && !raggiunte[s]) {
          raggiunte[s] = true;
          if (typeof gtag === 'function') { gtag('event', 'scroll_depth', { percent_scroll: s }); }
        }
      });
    }, { passive: true });
  }

  // Lo script e' caricato con defer, quindi il DOM c'e' gia'; il ramo
  // DOMContentLoaded resta per sicurezza se qualcuno lo includesse senza defer.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', avvia);
  } else {
    avvia();
  }
})();
