/* DAOP - la mappa di un elenco (oggi: luoghi.html).
 *
 * E' una VISTA dell'elenco, non una seconda copia dei dati: i segnaposto sono
 * le righe che i filtri della pagina lasciano visibili, lette dal DOM
 * (data-lat/data-lon, gli stessi di "vicino a me"), e toccarne uno apre la
 * riga vera. Cosi' filtri, raggio e ricerca valgono anche qui senza una riga
 * di codice in piu', e non esiste un secondo elenco da tenere allineato.
 *
 * Perche' e' fatta cosi', in breve (il lungo sta in CLAUDE.md):
 *  - si carica SOLO al tocco: libreria (~280 KB compressi, ospitata su
 *    daop.it) e mappe di sfondo non partono finche' nessuno apre la mappa. Chi
 *    non la usa non paga niente, ne' in byte ne' in privacy;
 *  - le mappe di sfondo sono di OpenFreeMap: niente chiave, niente cookie,
 *    niente tetto mensile, uso commerciale ammesso col credito a OpenStreetMap.
 *    Un tetto mensile sarebbe il difetto del bucket da 5 GB: si spegne da solo;
 *  - si sposta con DUE dita (cooperativeGestures): con un dito si continua a
 *    scorrere la pagina. Una mappa dentro una pagina che scorre, senza, ruba il
 *    gesto a chi scorre - e' il primo problema che NN/g trova sulle mappe su
 *    telefono;
 *  - i segnaposto sono tutti uguali per chi paga e per chi no: una mappa e' un
 *    altro modo di mettere in fila i risultati, e la posizione su daop.it non
 *    si vende (vedi #come-ordiniamo). Il colore e' quello della categoria.
 *
 * Non chiama gtag: emette `daop:mappa` e daop-track.js lo raccoglie, come per
 * "vicino a me".
 */
(function () {
  'use strict';

  var LIB = '/assets/vendor/maplibre-gl-5.24.0/maplibre-gl.js';
  var CSS = '/assets/vendor/maplibre-gl-5.24.0/maplibre-gl.css';
  var STILE = 'https://tiles.openfreemap.org/styles/positron';
  // Sull'intero Piemonte meridionale, per il primo disegno prima dei dati.
  var CENTRO = [8.4, 44.6];
  var MAX_ELENCO = 8;

  var ITALIANO = {
    'CooperativeGesturesHandler.WindowsHelpText': 'Usa Ctrl + rotellina per ingrandire la mappa',
    'CooperativeGesturesHandler.MacHelpText': 'Usa ⌘ + rotellina per ingrandire la mappa',
    'CooperativeGesturesHandler.MobileHelpText': 'Usa due dita per spostare la mappa',
    'NavigationControl.ZoomIn': 'Ingrandisci',
    'NavigationControl.ZoomOut': 'Riduci',
    'NavigationControl.ResetBearing': 'Riporta a nord',
    'AttributionControl.ToggleAttribution': 'Mostra i crediti',
    'AttributionControl.MapFeedback': 'Segnala un errore sulla mappa',
    'Popup.Close': 'Chiudi'
  };

  var caricamento = null;
  function carica() {
    if (window.maplibregl) return Promise.resolve(window.maplibregl);
    if (caricamento) return caricamento;
    caricamento = new Promise(function (ok, ko) {
      var l = document.createElement('link');
      l.rel = 'stylesheet';
      l.href = CSS;
      document.head.appendChild(l);
      var s = document.createElement('script');
      s.src = LIB;
      s.onload = function () { window.maplibregl ? ok(window.maplibregl) : ko(new Error('libreria')); };
      s.onerror = function () { ko(new Error('libreria')); };
      document.head.appendChild(s);
    });
    // Un secondo tocco dopo un errore deve poter riprovare.
    caricamento.catch(function () { caricamento = null; });
    return caricamento;
  }

  window.daopMappa = {
    /* opz.nodo     il contenitore della mappa (parte `hidden`)
       opz.voci     funzione: le voci visibili adesso, nell'ordine della pagina
       opz.scheda   funzione(voce) -> {titolo, sotto}: il testo del fumetto
       opz.vai      funzione(voce): apre la riga nella pagina
       opz.tipo     'luoghi' (va nell'evento daop:mappa)
       Torna {apri, chiudi, aggiorna, aperta}. */
    avvia: function (opz) {
      var nodo = opz.nodo;
      if (!nodo) return null;
      var tela = document.createElement('div');
      tela.className = 'dm-tela';
      var avviso = document.createElement('p');
      avviso.className = 'dm-avviso';
      avviso.setAttribute('role', 'status');
      nodo.appendChild(tela);
      nodo.appendChild(avviso);

      var mappa = null, pronta = false, aperta = false, segnalata = false;
      var voci = [], attesa = null, colori = new Map();

      function colore(v) {
        if (!colori.has(v)) {
          var c = getComputedStyle(v).getPropertyValue('--cat-color').trim();
          colori.set(v, c || '#7e8c99');
        }
        return colori.get(v);
      }

      /* I dati si calcolano anche prima che la mappa sia pronta, e il conto sta
         in data-punti: e' quello che le prove leggono, e cosi' non dipendono
         dal fatto che le mappe di sfondo rispondano. */
      function dati() {
        voci = [];
        var f = [];
        opz.voci().forEach(function (v) {
          var la = parseFloat(v.getAttribute('data-lat'));
          var lo = parseFloat(v.getAttribute('data-lon'));
          if (!isFinite(la) || !isFinite(lo)) return;
          f.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [lo, la] },
                   properties: { i: voci.length, c: colore(v) } });
          voci.push(v);
        });
        nodo.setAttribute('data-punti', String(f.length));
        return { type: 'FeatureCollection', features: f };
      }

      function inquadra(fc, anima) {
        if (!fc.features.length) return;
        var b = new window.maplibregl.LngLatBounds();
        fc.features.forEach(function (x) { b.extend(x.geometry.coordinates); });
        mappa.fitBounds(b, { padding: 36, maxZoom: 13, animate: !!anima, duration: anima ? 400 : 0 });
      }

      function disegna(anima) {
        var fc = dati();
        avviso.textContent = fc.features.length ? '' : 'Nessun luogo da mostrare con questi filtri.';
        if (!pronta) return;
        mappa.getSource('dm').setData(fc);
        inquadra(fc, anima);
      }

      /* Il fumetto si costruisce col DOM e textContent, mai con innerHTML: i
         nomi vengono da un foglio compilato a mano. */
      function fumetto(lista, lngLat) {
        var box = document.createElement('div');
        box.className = 'dm-pop';
        lista.slice(0, MAX_ELENCO).forEach(function (v) {
          var s = opz.scheda(v);
          var a = document.createElement('a');
          a.href = '#' + v.id;
          a.className = 'dm-voce';
          var b = document.createElement('b');
          b.textContent = s.titolo;
          var i = document.createElement('span');
          i.textContent = s.sotto;
          a.appendChild(b);
          a.appendChild(i);
          a.addEventListener('click', function (ev) {
            ev.preventDefault();
            pop.remove();
            opz.vai(v);
          });
          box.appendChild(a);
        });
        if (lista.length > MAX_ELENCO) {
          var p = document.createElement('p');
          p.className = 'dm-altri';
          p.textContent = 'e altri ' + (lista.length - MAX_ELENCO) + ': ingrandisci la mappa';
          box.appendChild(p);
        }
        var pop = new window.maplibregl.Popup({ offset: 10, maxWidth: '280px' })
          .setLngLat(lngLat).setDOMContent(box).addTo(mappa);
      }

      function crea(ml) {
        mappa = new ml.Map({
          container: tela,
          style: STILE,
          center: CENTRO,
          zoom: 7.5,
          cooperativeGestures: true,
          dragRotate: false,
          pitchWithRotate: false,
          touchPitch: false,
          attributionControl: { compact: true },
          locale: ITALIANO
        });
        mappa.touchZoomRotate.disableRotation();
        mappa.addControl(new ml.NavigationControl({ showCompass: false }), 'top-right');
        mappa.on('error', function (e) {
          if (!pronta && e && e.error && /style|Failed to fetch|NetworkError/i.test(String(e.error.message || e.error))) {
            avviso.textContent = 'La mappa non si è caricata. L\'elenco qui sotto funziona lo stesso.';
          }
        });
        mappa.on('load', function () {
          mappa.addSource('dm', { type: 'geojson', data: dati(), cluster: true,
                                  clusterRadius: 38, clusterMaxZoom: 12 });
          mappa.addLayer({ id: 'dm-gruppi', type: 'circle', source: 'dm',
            filter: ['has', 'point_count'],
            paint: { 'circle-color': '#2d4a5c', 'circle-opacity': 0.9,
                     'circle-radius': ['step', ['get', 'point_count'], 14, 10, 18, 50, 23],
                     'circle-stroke-width': 2, 'circle-stroke-color': '#fff' } });
          /* Il numero sul gruppo usa un carattere che lo stile ha davvero:
             chiederne uno che il server non ha lascia il cerchio muto e riempie
             la console di errori. Se lo stile non ne ha nessuno, niente numero:
             il cerchio piu' grande dice lo stesso. */
          var font = null;
          (mappa.getStyle().layers || []).some(function (l) {
            var f = l.layout && l.layout['text-font'];
            if (Array.isArray(f) && typeof f[0] === 'string') { font = f; return true; }
            return false;
          });
          if (font && mappa.getStyle().glyphs) {
            mappa.addLayer({ id: 'dm-numeri', type: 'symbol', source: 'dm',
              filter: ['has', 'point_count'],
              layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-font': font,
                        'text-size': 12, 'text-allow-overlap': true },
              paint: { 'text-color': '#fff' } });
          }
          mappa.addLayer({ id: 'dm-punti', type: 'circle', source: 'dm',
            filter: ['!', ['has', 'point_count']],
            paint: { 'circle-color': ['get', 'c'], 'circle-radius': 8,
                     'circle-stroke-width': 2, 'circle-stroke-color': '#fff' } });

          mappa.on('click', 'dm-gruppi', function (e) {
            var g = e.features[0];
            var src = mappa.getSource('dm');
            var id = g.properties.cluster_id;
            src.getClusterExpansionZoom(id).then(function (z) {
              // Tanti posti nello stesso punto (lo stesso indirizzo, o un parco
              // con dieci attivita') non si separano ingrandendo: si elencano.
              if (z > 16 || z <= mappa.getZoom()) {
                return src.getClusterLeaves(id, 50, 0).then(function (ff) {
                  fumetto(ff.map(function (x) { return voci[x.properties.i]; }).filter(Boolean),
                          g.geometry.coordinates);
                });
              }
              mappa.easeTo({ center: g.geometry.coordinates, zoom: z });
            }).catch(function () {});
          });
          mappa.on('click', 'dm-punti', function (e) {
            var viste = {};
            var lista = e.features.map(function (x) { return voci[x.properties.i]; })
              .filter(function (v) { if (!v || viste[v.id]) return false; viste[v.id] = 1; return true; });
            if (lista.length) fumetto(lista, e.features[0].geometry.coordinates);
          });
          ['dm-gruppi', 'dm-punti'].forEach(function (id) {
            mappa.on('mouseenter', id, function () { mappa.getCanvas().style.cursor = 'pointer'; });
            mappa.on('mouseleave', id, function () { mappa.getCanvas().style.cursor = ''; });
          });
          pronta = true;
          nodo.setAttribute('data-pronta', '1');
          disegna(false);
        });
      }

      function apri() {
        aperta = true;
        nodo.hidden = false;
        if (!segnalata) {
          segnalata = true;
          try {
            document.dispatchEvent(new CustomEvent('daop:mappa', { detail: { tipo: opz.tipo || '' } }));
          } catch (e) { /* browser antichi: la mappa funziona lo stesso */ }
        }
        dati();
        if (mappa) { mappa.resize(); disegna(false); return; }
        avviso.textContent = 'Carico la mappa…';
        carica().then(function (ml) {
          avviso.textContent = '';
          try { crea(ml); } catch (e) {
            // Senza WebGL MapLibre non parte: lo si dice, e l'elenco resta.
            avviso.textContent = 'Questo browser non riesce a mostrare la mappa. L\'elenco qui sotto funziona lo stesso.';
          }
        }, function () {
          avviso.textContent = 'La mappa non si è caricata. L\'elenco qui sotto funziona lo stesso.';
        });
      }

      function chiudi() {
        aperta = false;
        nodo.hidden = true;
      }

      /* La ricerca chiama i filtri a ogni lettera: la mappa si rifa' quando
         chi scrive si ferma, non a ogni tasto. */
      function aggiorna() {
        if (!aperta) return;
        clearTimeout(attesa);
        attesa = setTimeout(function () { disegna(true); }, 250);
      }

      return { apri: apri, chiudi: chiudi, aggiorna: aggiorna,
               aperta: function () { return aperta; } };
    }
  };
})();
