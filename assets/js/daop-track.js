/* DAOP - tracciamento dei clic che GA4 da solo non vede.
 *
 * Perche' esiste come file esterno e non come blocco inline: il blocco inline
 * viveva nelle pagine scritte a mano, e sulle ~280 pagine generate ricopiarlo
 * avrebbe voluto dire 2 KB in piu' su ognuna e dodici copie da tenere
 * allineate. Cosi' e' una richiesta sola, in cache dalla seconda pagina in poi.
 * Dal 12/08/2026 le copie inline non ci sono piu': questo file e' l'unico
 * posto in cui si scrivono i clic, come cookie-consent.js e' l'unico posto in
 * cui si inizializza GA4.
 *
 * Cosa NON serve tracciare qui: la navigazione interna. Ogni pagina del sito
 * manda gia' un page_view (lo fa cookie-consent.js dopo il consenso), quindi
 * "da questa scheda dove vanno dopo" si legge gia' in GA4 con un'esplorazione
 * di percorso. Qui stanno solo i clic che NON producono un page_view: quelli
 * che portano fuori dal sito o che aprono un'app.
 *
 * gtag esiste solo dopo il consenso ai cookie: ogni chiamata e' protetta, e
 * senza consenso lo script gira a vuoto senza errori.
 */
(function () {
  'use strict';

  if (window.__daopTrackAttivo) return; // due include = un solo tracciamento
  window.__daopTrackAttivo = true;

  /* ── Contesto della pagina ─────────────────────────────────────────────
     I generatori stampano tre meta sulle pagine che parlano di un evento o
     di un comune. Dove non ci sono (home, rubriche, libri...) i campi
     restano vuoti e semplicemente non vengono mandati: GA4 non riceve
     parametri con valore vuoto, cosi' i report non si riempiono di "(not
     set)" sulle pagine per cui la domanda non ha senso. */
  function meta(nome) {
    var m = document.querySelector('meta[name="' + nome + '"]');
    var v = m && m.getAttribute('content');
    return v ? v.trim() : '';
  }

  var CTX = {
    event_title: meta('daop:evento'),
    event_city: meta('daop:citta'),
    event_province: meta('daop:provincia')
  };

  // Stesso motivo di cookie-consent.js: "/index.html" e "/" sono la stessa
  // pagina e devono contare come una sola riga anche negli eventi di clic.
  function percorso() {
    return location.pathname.replace(/\/index\.html$/i, '/') || '/';
  }

  /* ── Invio ─────────────────────────────────────────────────────────────
     `event_name` non viene mandato come parametro: in GA4 e' gia' il nome
     dell'evento stesso (la dimensione "Nome evento"), e un parametro
     personalizzato con lo stesso nome andrebbe a sbattere contro quella
     dimensione. Chi legge il report lo vede comunque, in colonna.
     `link_url` resta accanto a `destination_url` per non spezzare la serie
     storica: le esplorazioni gia' salvate in GA4 leggono quel nome. */
  function track(nome, href) {
    // `gtag` esiste sempre (e' lo stub che accoda): la domanda vera e' se
    // l'utente ha acconsentito. Il flag lo mette cookie-consent.js.
    if (!window.daopConsensoAnalytics || typeof gtag !== 'function') return;
    var p = {
      page_path: percorso(),
      destination_url: href,
      link_url: href
    };
    for (var k in CTX) { if (CTX[k]) p[k] = CTX[k]; }
    gtag('event', nome, p);
  }

  /* ── Che cosa e' stato cliccato ────────────────────────────────────────
     L'ordine conta: i casi specifici stanno prima di quello generico, se no
     una locandina su Supabase finirebbe in "sito organizzatore". */
  var IMMAGINE = /\.(jpe?g|png|webp|avif|gif)(\?.*)?$/i;

  function nome_evento(href) {
    if (href.indexOf('mailto:') === 0) return 'click_email';
    if (href.indexOf('tel:') === 0) return 'click_telefono';
    if (href.indexOf('ginettoapp.it') !== -1) return 'apri_ginetto';
    if (href.indexOf('gioco.sane-italia.it') !== -1) return 'gioca_ora';
    if (href.indexOf('instagram.com') !== -1 ||
        href.indexOf('facebook.com') !== -1 ||
        href.indexOf('youtube.com') !== -1) return 'click_social';
    // I tre sotto valgono soprattutto sulle pagine evento: dicono se la
    // scheda ha fatto il suo mestiere. Chi apre la mappa o si segna la data
    // sul calendario ci sta andando davvero, ed e' un segnale piu' forte di
    // qualunque tempo sulla pagina.
    if (href.indexOf('google.com/maps') !== -1) return 'click_come_arrivare';
    if (href.indexOf('calendar.google.com') !== -1) return 'aggiungi_calendario';
    if (href.indexOf('/storage/v1/object/public/locandine/') !== -1 ||
        href.indexOf('/assets/miniature/') !== -1) return 'click_locandina';
    if (href.slice(-4).toLowerCase() === '.pdf') return 'scarica_materiale';
    if (href.indexOf('amazon.') !== -1 || href.indexOf('amzn.') !== -1) return 'click_amazon';
    // Generico: qualunque altro link che porta fuori da daop.it. Sulle schede
    // evento e' il sito di chi organizza, scritto nella descrizione o nei
    // recapiti; e' l'unico posto da cui puo' arrivare un link esterno.
    if (/^https?:\/\//i.test(href) && href.indexOf('daop.it') === -1) {
      if (IMMAGINE.test(href)) return 'click_locandina';
      return 'click_sito_organizzatore';
    }
    return null;
  }

  /* ── Antirimbalzo ──────────────────────────────────────────────────────
     Un clic solo deve valere un evento solo. Serve perche' su alcuni link
     convivono piu' comportamenti (locandina.js apre il riquadro, il link
     resta un href vero) e perche' un doppio clic involontario e' comune sui
     telefoni. Stesso evento + stessa destinazione entro 800 ms: si scarta. */
  var ultimo = { chiave: '', quando: 0 };
  function invia(nome, href) {
    var chiave = nome + '|' + href;
    var ora = Date.now();
    if (chiave === ultimo.chiave && ora - ultimo.quando < 800) return;
    ultimo.chiave = chiave;
    ultimo.quando = ora;
    track(nome, href);
  }

  function avvia() {
    /* Un ascoltatore solo, in delega sul document, invece di uno per ogni
       <a>: su eventi.html i link sono ~1.500 e attaccarli a mano era lavoro
       al caricamento sulla pagina piu' pesante del sito (11.000 nodi, il
       punto dolente documentato in CLAUDE.md). In delega il costo e' zero e
       vale anche per i link che compaiono dopo, senza riagganciare niente. */
    document.addEventListener('click', function (ev) {
      var a = ev.target.closest && ev.target.closest('a[href]');
      if (a) {
        var href = a.getAttribute('href') || '';
        var nome = nome_evento(href);
        if (nome) invia(nome, href);
        return;
      }
      // Sulle schede evento la locandina non e' dentro un link: e' l'immagine
      // grande in colonna, che locandina.js apre nel riquadro. Senza questo
      // ramo il clic piu' significativo della scheda non si vedrebbe.
      var img = ev.target.closest && ev.target.closest('img.ev-loc');
      if (img) invia('click_locandina', img.getAttribute('src') || '');
    }, true);

    /* "Vicino a me". Il filtro per distanza (daop-vicino.js) non chiama gtag
       da solo: emette un evento DOM e lo raccogliamo qui, cosi' gtag resta
       scritto in un posto solo - la stessa regola per cui cookie-consent.js e'
       l'unico posto in cui GA4 si inizializza.

       NON si manda mai la posizione. Partono due cose sole: COME e' stato
       scelto il centro (gps, comune, gradino) e QUANTI chilometri. Le
       coordinate restano nel browser, che e' anche quello che la pagina
       promette a chi la usa: mandarle a GA4 renderebbe quella riga una bugia.

       A cosa serve misurarlo: a decidere se la funzione vale su altre pagine,
       e soprattutto se chi la usa poi apre una scheda. Il resto del percorso
       si legge gia' con i page_view. */
    document.addEventListener('daop:vicino', function (ev) {
      var d = (ev && ev.detail) || {};
      var p = { page_path: percorso() };
      if (d.metodo) p.metodo_posizione = d.metodo;
      if (d.raggio) p.raggio_km = d.raggio;
      for (var k in CTX) { if (CTX[k]) p[k] = CTX[k]; }
      // Stesso antirimbalzo dei clic: chi prova tre gradini di fila e' una
      // persona che sta scegliendo, non tre eventi.
      var chiave = 'vicino|' + d.metodo + '|' + d.raggio;
      var ora = Date.now();
      if (chiave === ultimo.chiave && ora - ultimo.quando < 800) return;
      ultimo.chiave = chiave;
      ultimo.quando = ora;
      if (!window.daopConsensoAnalytics || typeof gtag !== 'function') return;
      gtag('event', 'vicino_a_me', p);
    });

    /* Profondita' di scroll: evento a 25/50/75/100%. Su una scheda evento
       dice se sono arrivati in fondo, dove stanno la firma e i link alle
       landing. E' voluto e NON e' un doppione dell'evento automatico
       `scroll` di GA4: quello scatta una volta sola, al 90%, e non distingue
       chi si ferma a meta'. Se in GA4 si vogliono vedere solo questi, si
       toglie "Scorrimenti" da Misurazione avanzata. */
    var soglie = [25, 50, 75, 100], raggiunte = {}, inCoda = false;
    window.addEventListener('scroll', function () {
      // Il calcolo legge scrollHeight/clientHeight, che forzano il layout:
      // farlo a ogni evento di scroll su un documento da 11.000 nodi si
      // sente. Una lettura per frame basta e avanza.
      if (inCoda) return;
      inCoda = true;
      requestAnimationFrame(function () {
        inCoda = false;
        var h = document.documentElement;
        var scrollabile = h.scrollHeight - h.clientHeight;
        if (scrollabile <= 0) return;
        var perc = (h.scrollTop || document.body.scrollTop) / scrollabile * 100;
        soglie.forEach(function (s) {
          if (perc >= s && !raggiunte[s]) {
            raggiunte[s] = true;
            if (window.daopConsensoAnalytics && typeof gtag === 'function') {
              gtag('event', 'scroll_depth', { percent_scroll: s, page_path: percorso() });
            }
          }
        });
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
