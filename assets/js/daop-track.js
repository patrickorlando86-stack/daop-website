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
 * Cosa NON serve tracciare qui: la navigazione interna qualunque. Ogni pagina
 * del sito manda gia' un page_view (lo fa cookie-consent.js dopo il consenso),
 * quindi "da questa scheda dove vanno dopo" si legge gia' in GA4 con
 * un'esplorazione di percorso. Qui stanno i clic che NON producono un
 * page_view: quelli che portano fuori dal sito o che aprono un'app.
 *
 * L'ECCEZIONE, dal 14/09/2026: i blocchi marcati `data-cta`. Il page_view dice
 * da quale PAGINA si arriva, non da quale BLOCCO, e non dice quante volte quel
 * blocco e' stato visto - quindi "il link ai corsi in coda alla scheda rende
 * o no?" non aveva risposta. Per quei blocchi, e solo per quelli, partono
 * `internal_cta_view` (una volta per pagina, quando il blocco e' a schermo) e
 * `internal_cta_click`. I nomi sono quelli proposti da Giovanni nell'analisi
 * del 14/09, apposta: chi legge i report e' lui.
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

  /* ── Contesto della RIGA ────────────────────────────────────────────────
     I meta qui sopra descrivono la PAGINA, e su quasi tutto il sito basta:
     una scheda evento parla di un evento solo. Su /corsi.html no — in una
     pagina sola convivono N societa' e N corsi, quindi "chi ha ricevuto
     questo clic" e' una domanda per elemento, non per documento.

     La risposta sta gia' nel DOM: il generatore stampa `data-org` sia sulla
     card del corso sia sulla scheda della realta' (e' lo stesso slug
     dell'ancora #r-pgs-roccavione che si manda su WhatsApp), piu'
     `data-org-nome` per il nome leggibile e `data-codice` per il codice del
     foglio. Qui si risale l'albero e basta: nessun elenco da tenere
     allineato, e un link che NON sta dentro una di quelle scatole — l'invito
     alle societa' in fondo, per dire — non prende l'attribuzione di nessuno,
     che e' il comportamento giusto.

     A cosa serve: a rispondere a una realta' "quanti hanno aperto la tua
     scheda, quanti sono andati sul tuo sito, quanti ti hanno chiamato"
     senza ricostruire ogni volta l'organizzatore da `destination_url`.

     `organizer_id` e' lo slug e NON deve mai cambiare: e' anche l'ancora che
     gira nei messaggi, e in GA4 un id nuovo vuol dire una serie storica che
     riparte da zero. Se nel foglio c'e' un CODICE, quello vince come
     `course_id` proprio per questo — un corso che si rinomina non perde il
     suo storico. */
  function contesto_riga(el) {
    var out = {};
    if (!el || !el.closest) return out;
    var box = el.closest('[data-org]');
    if (box) {
      var oid = box.getAttribute('data-org') || '';
      var onome = box.getAttribute('data-org-nome') || '';
      if (oid) out.organizer_id = oid;
      if (onome) out.organizer_name = onome;
    }
    var card = el.closest('.event-card[data-org]');
    if (card) {
      var cid = card.getAttribute('data-codice') || card.id || '';
      if (cid) out.course_id = cid;
      var n = card.querySelector('.ev-name');
      var testo = n && (n.textContent || '').trim();
      if (testo) out.course_name = testo;
    }
    /* Le schede di /luoghi.html. Stessi parametri dei corsi, e non una
       dimensione nuova, perche' la domanda e' la stessa - "a quale realta'
       va questo clic" - e le quattro dei corsi sono gia' registrate in GA4.
       L'id non si stampa in un attributo: e' l'id della riga, che esiste gia'
       (#lg-...), quindi 890 righe non pagano un byte in piu'. Le copie nel
       riquadro Sponsorizzati hanno "-ev" in coda: si toglie, se no lo stesso
       posto sarebbe due righe nei report. `posizione` dice da dove e' partito
       il clic, ed e' la prova di quanto vale il riquadro a chi lo compra. */
    var lg = !box && el.closest('.lg-row');
    if (lg) {
      var lid = (lg.id || '').replace(/-ev$/, '');
      if (lid) out.organizer_id = lid;
      var ln = lg.querySelector('.lg-nome');
      var lt = ln && (ln.textContent || '').trim();
      if (lt) out.organizer_name = lt;
      out.posizione = lg.closest('.lg-vetrina') ? 'sponsorizzati' : 'elenco';
    }
    // La riga "Sponsorizzato" in coda a una scheda evento: il posto e' quello
    // dell'ancora, cosi' il report lo mette sulla stessa riga delle aperture.
    var sp = el.closest('.ev-spons');
    if (sp) {
      var sa = sp.querySelector('a[href*="#lg-"]');
      var sid = sa && (sa.getAttribute('href') || '').split('#')[1];
      if (sid) out.organizer_id = sid;
      if (sa && sa.textContent) out.organizer_name = sa.textContent.trim();
      out.posizione = 'scheda_evento';
    }
    return out;
  }

  // Stesso motivo di cookie-consent.js: "/index.html" e "/" sono la stessa
  // pagina e devono contare come una sola riga anche negli eventi di clic.
  function percorso() {
    return location.pathname.replace(/\/index\.html$/i, '/') || '/';
  }

  /* In quale famiglia del sito porta un link interno, per `destination_area`.
     `destination_url` c'e' gia' e dice la pagina esatta; questo raggruppa, cosi'
     "quanti vanno ai corsi" non chiede un filtro scritto a mano in GA4. Torna
     '' per un link che esce dal sito: quelli hanno gia' il loro evento.
     `evento` e' la scheda singola, `eventi` qualunque elenco di eventi. */
  function area_destinazione(href) {
    var u;
    try { u = new URL(href, location.href); } catch (e) { return ''; }
    if (u.host !== location.host && u.host.indexOf('daop.it') === -1) return '';
    // Aperta da file:// su Windows, "/corsi.html" si risolve in /C:/corsi.html
    // (la trappola gia' scritta in tests/_aiuto.js): online non capita mai, ma
    // senza questa riga la prova vedrebbe "altro" dove il sito dice "corsi".
    var p = u.pathname.replace(/^\/[A-Za-z]:(?=\/)/, '');
    if (/^\/corsi(\.html$|\/)/.test(p)) return 'corsi';
    if (p === '/luoghi.html' || p === '/piscine.html') return 'luoghi';
    if (p === '/ginetto.html') return 'ginetto';
    if (p.indexOf('/centri-') === 0) return 'centri';
    if (p.indexOf('/eventi/comune/') === 0 ||
        /^\/eventi\/(oggi|weekend)[^/]*\.html$/.test(p)) return 'eventi';
    if (p.indexOf('/eventi/') === 0) return 'evento';
    if (p === '/eventi.html' || /^\/(sagre|eventi)-provincia-/.test(p)) return 'eventi';
    return 'altro';
  }

  /* ── Invio ─────────────────────────────────────────────────────────────
     `event_name` non viene mandato come parametro: in GA4 e' gia' il nome
     dell'evento stesso (la dimensione "Nome evento"), e un parametro
     personalizzato con lo stesso nome andrebbe a sbattere contro quella
     dimensione. Chi legge il report lo vede comunque, in colonna.
     `link_url` resta accanto a `destination_url` per non spezzare la serie
     storica: le esplorazioni gia' salvate in GA4 leggono quel nome. */
  function track(nome, href, el) {
    // `gtag` esiste sempre (e' lo stub che accoda): la domanda vera e' se
    // l'utente ha acconsentito. Il flag lo mette cookie-consent.js.
    if (!window.daopConsensoAnalytics || typeof gtag !== 'function') return;
    var p = { page_path: percorso() };
    // `apri_corso` non porta da nessuna parte: mandare una destinazione vuota
    // riempirebbe il report di "(not set)" sulla meta' degli eventi.
    if (href) { p.destination_url = href; p.link_url = href; }
    for (var k in CTX) { if (CTX[k]) p[k] = CTX[k]; }
    var riga = contesto_riga(el);
    for (var j in riga) { p[j] = riga[j]; }
    /* Da quale blocco marcato e' partito il clic (vedi internal_cta_view in
       avvia()). Vale anche per `apri_ginetto` e `click_sponsorizzato`: la
       domanda "da quale posto della pagina" e' la stessa. */
    var blocco = el && el.closest && el.closest('[data-cta]');
    if (blocco) p.cta_id = blocco.getAttribute('data-cta');
    if (nome === 'internal_cta_click') p.destination_area = area_destinazione(href);
    /* Quale guida. Sta in un attributo e non si deduce dal nome del file:
       "estivi-2027.pdf" andrebbe spezzato in due qui dentro, e il giorno che il
       nome cambia il report cambia in silenzio. Stessa ragione di
       `organizer_name`. Va registrata in GA4 come dimensione evento prima di
       pubblicare: non e' retroattiva. */
    if (el && el.getAttribute) {
      var g = el.getAttribute('data-guida');
      if (g) { p.stagione = g; }
    }
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
    /* La guida stagionale ha un nome suo e sta PRIMA del ramo generico dei
       PDF. Nel secchio `scarica_materiale` finirebbe insieme a qualunque
       allegato di qualunque organizzatore, e l'unica domanda che la guida pone
       — quanti se la portano via ogni mille visite — si potrebbe rispondere
       solo filtrando `destination_url` a mano, cioe' mai. E' esattamente il
       difetto che l'invito al canale ha avuto per una settimana. */
    if (href.indexOf('/guide/') !== -1 &&
        href.slice(-4).toLowerCase() === '.pdf') return 'scarica_guida';
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
  function invia(nome, href, el) {
    // L'id della scatola entra nella chiave perche' `apri_corso` non ha una
    // destinazione: senza, due corsi aperti in fila entro 800 ms sarebbero la
    // stessa chiave e il secondo si perderebbe.
    var box = el && el.closest && (el.closest('[data-org]') || el.closest('.lg-row'));
    var chiave = nome + '|' + href + '|' + ((box && box.id) || '');
    var ora = Date.now();
    if (chiave === ultimo.chiave && ora - ultimo.quando < 800) return;
    ultimo.chiave = chiave;
    ultimo.quando = ora;
    track(nome, href, el);
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
        // L'unico link INTERNO che si conta, e il perche' e' commerciale: e'
        // uno spazio venduto, e a chi lo compra si deve poter dire quante
        // volte e' stato toccato. Il page_view di /luoghi.html che segue non
        // lo direbbe - non sa da quale riga di quale scheda si e' arrivati.
        if (a.closest('.ev-spons')) { invia('click_sponsorizzato', href, a); return; }
        var nome = nome_evento(href);
        if (nome) { invia(nome, href, a); return; }
        // Un link interno dentro un blocco marcato. Fuori da quei blocchi la
        // navigazione interna resta affidata ai page_view, vedi in testa.
        if (a.closest('[data-cta]') && area_destinazione(href)) {
          invia('internal_cta_click', href, a);
        }
        return;
      }
      /* L'APERTURA DI UNA SCHEDA LUOGO, il denominatore che mancava a
         /luoghi.html: GA4 contava i clic DALLA scheda (mappe, telefono, sito)
         ma non quante volte era stata aperta, quindi a un cliente si poteva
         dire "47 hanno chiesto le indicazioni" e non su quante. Stessa regola
         di apri_corso qui sotto: al momento del capture il <details> e' ancora
         nello stato vecchio, quindi `open` falso vuol dire che si sta aprendo,
         e richiudere non conta. */
      var sum = ev.target.closest && ev.target.closest('.lg-row > summary');
      if (sum) {
        if (!sum.parentElement.open) invia('apri_luogo', '', sum.parentElement);
        return;
      }
      /* L'APERTURA DI UNA SCHEDA CORSO, che e' il denominatore di tutto il
         resto. /corsi.html e' UNA pagina: il suo page_view dice "qualcuno ha
         aperto l'elenco", non "qualcuno ha guardato i corsi della PGS
         Roccavione". Senza questo evento a una realta' si potrebbe dire "3
         clic al tuo sito" ma non su quante volte, che e' l'unica forma in cui
         quel numero vuol dire qualcosa — lo stesso buco gia' scritto in
         CLAUDE.md per le schede di luoghi.html.

         Si conta solo l'APERTURA: al momento del capture `aria-expanded` ha
         ancora il valore vecchio, quindi "false" vuol dire che sta aprendo.
         Chiudere una riga non e' un secondo interessamento.

         Il selettore chiede `data-org`, che oggi lo stampa il solo
         genera_corsi.py: le ~300 schede evento hanno le stesse `.ev-row` e
         contarle qui vorrebbe dire moltiplicare gli eventi su tutto il sito
         per una domanda che li' nessuno ha fatto. */
      var apri = ev.target.closest && ev.target.closest('.event-card[data-org] .ev-row');
      if (apri) {
        if (apri.getAttribute('aria-expanded') === 'false') invia('apri_corso', '', apri);
        return;
      }
      // Sulle schede evento la locandina non e' dentro un link: e' l'immagine
      // grande in colonna, che locandina.js apre nel riquadro. Senza questo
      // ramo il clic piu' significativo della scheda non si vedrebbe.
      var img = ev.target.closest && ev.target.closest('img.ev-loc');
      if (img) invia('click_locandina', img.getAttribute('src') || '', img);
    }, true);

    /* LA VISTA DI UN BLOCCO MARCATO (`data-cta`), una volta per pagina.
       E' il denominatore del clic: 20 clic sul link ai corsi non dicono niente
       se non si sa se il blocco l'hanno visto in cento o in diecimila. Prima
       quel numero si stimava da scroll_depth e dall'altezza misurata a mano
       del blocco; cosi' si legge.

       "Visto" vuol dire meta' del blocco a schermo, oppure - per un blocco
       piu' alto dello schermo - una fetta pari al 40% dello schermo.

       Senza consenso non si manda e NON si segna come visto: il blocco resta
       osservato, e al prossimo passaggio di soglia (basta scorrere) si
       riprova. Segnarlo lo stesso vorrebbe dire perdere per sempre la vista di
       chi accetta il banner dopo aver gia' visto il blocco, cioe' contare clic
       senza la loro vista.

       Costa zero sulle pagine che non hanno blocchi marcati: senza elementi
       l'osservatore non nasce nemmeno. */
    var blocchi = document.querySelectorAll('[data-cta]');
    if (blocchi.length && 'IntersectionObserver' in window) {
      var visti = {};
      var oss = new IntersectionObserver(function (voci) {
        voci.forEach(function (v) {
          if (!v.isIntersecting) return;
          if (v.intersectionRatio < 0.5 &&
              v.intersectionRect.height < window.innerHeight * 0.4) return;
          var id = v.target.getAttribute('data-cta');
          if (visti[id]) { oss.unobserve(v.target); return; }
          if (!window.daopConsensoAnalytics || typeof gtag !== 'function') return;
          visti[id] = true;
          oss.unobserve(v.target);
          var p = { page_path: percorso(), cta_id: id };
          for (var k in CTX) { if (CTX[k]) p[k] = CTX[k]; }
          gtag('event', 'internal_cta_view', p);
        });
      }, { threshold: [0, 0.25, 0.5, 0.75, 1] });
      [].forEach.call(blocchi, function (b) { oss.observe(b); });
    }

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

    /* La mappa di luoghi.html (daop-mappa.js). Come "vicino a me", il modulo
       non chiama gtag: emette un evento DOM. Parte una volta per pagina, alla
       prima apertura: e' il numero che dice se la mappa serve, e va letto
       contro i page_view di /luoghi.html con la regola dei 2,5 per utente. */
    document.addEventListener('daop:mappa', function (ev) {
      if (!window.daopConsensoAnalytics || typeof gtag !== 'function') return;
      var d = (ev && ev.detail) || {};
      var p = { page_path: percorso() };
      if (d.tipo) p.destination_area = d.tipo;
      for (var k in CTX) { if (CTX[k]) p[k] = CTX[k]; }
      gtag('event', 'apri_mappa', p);
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
