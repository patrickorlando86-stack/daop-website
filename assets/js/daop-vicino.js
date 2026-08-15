/* DAOP - "Vicino a me": filtro per distanza.
 *
 * Perche' esiste come file esterno: la funzione e' nata dentro eventi.html il
 * 15/08/2026, ma il JS in fondo a quella pagina non passa da _guscio() (che
 * ricopia solo <style>, nav e footer), quindi le pagine generate non lo
 * vedevano. Ricopiarlo in quattordici template sarebbe stato quattordici copie
 * da tenere allineate: e' la stessa ragione per cui daop-track.js e'
 * un file solo.
 *
 * Perche' il filtro esiste: la tendina "provincia" non risponde a "vicino".
 * Misurato da Alessandria, dei 128 eventi in provincia di AL la mediana sta a
 * 25 km e il massimo a 55, e 14 eventi entro 25 km sono in provincia di Asti.
 * La provincia include il lontano ed esclude il vicino.
 *
 * Il modulo non sa come si nasconde una riga: l'agenda usa una classe, le
 * pagine di intenzione l'attributo `hidden`. Espone `entro(voce)` e la pagina
 * lo somma ai propri filtri. E non manda niente a GA4: emette un evento DOM
 * `daop:vicino`, che daop-track.js raccoglie - cosi' gtag resta scritto in un
 * posto solo, come cookie-consent.js e' l'unico posto in cui GA4 si
 * inizializza.
 */
(function () {
  'use strict';

  /* I gradini sono fissi e non uno slider: su un telefono uno slider e'
     impreciso e i risultati saltano comunque a scatti. Ognuno porta il suo
     conteggio, perche' scegliere fra "20 km" e "30 km" senza sapere che sono
     26 e 135 eventi e' scegliere al buio. */
  var STEPS = [10, 20, 30, 50];

  /* Stessa soglia di MIN_FILTRI nel generatore: sotto questo numero di voci si
     scorre prima la lista che a decidere in un controllo. */
  var MIN_VOCI = 12;

  /* Il gradino di partenza e' il primo che ha almeno tanti eventi: da Cuneo
     entro 10 km ce ne sono 4, e una pagina che nasce vuota e' il difetto
     tipico di questi filtri nelle zone rade. */
  var SOGLIA_PARTENZA = 5;

  function distanza(la1, lo1, la2, lo2) {
    var R = 6371, r = Math.PI / 180;
    var dLa = (la2 - la1) * r, dLo = (lo2 - lo1) * r;
    var a = Math.sin(dLa / 2) * Math.sin(dLa / 2) +
      Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin(dLo / 2) * Math.sin(dLo / 2);
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  function norm(s) {
    return (s || '').toLowerCase().normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
  }

  function scriviKm(d) {
    return d < 1 ? 'meno di 1 km' : Math.round(d) + ' km';
  }

  window.daopVicino = {
    /* opz.voci      elementi con data-lat/data-lon (righe o schede)
       opz.alCambio  la pagina rifa' i suoi filtri
       opz.riga      dove appendere la distanza dentro una voce (opzionale)
       Torna null se il controllo non si e' acceso: la pagina prosegue senza. */
    avvia: function (opz) {
      var nodo = document.getElementById('ev-geo');
      if (!nodo) return null;

      var voci = (opz.voci || []).filter(function (v) {
        return v.getAttribute('data-lat') && v.getAttribute('data-lon');
      });
      if (voci.length < MIN_VOCI) return null;

      var go = document.getElementById('ev-geo-go');
      var alt = document.getElementById('ev-geo-alt');
      var campo = document.getElementById('ev-geo-q');
      var lista = document.getElementById('ev-geo-list');
      var da = document.getElementById('ev-geo-from');
      var chips = document.getElementById('ev-geo-chips');
      var azzera = document.getElementById('ev-geo-clear');
      var hint = document.getElementById('ev-geo-hint');
      var nota = document.getElementById('ev-geo-note');

      var centro = null, raggio = null, comuni = null, richiesta = 0;
      var dist = new Map();
      var alCambio = opz.alCambio || function () {};

      function segnala(quale, extra) {
        var d = { metodo: quale, raggio: raggio };
        for (var k in extra) d[k] = extra[k];
        try {
          document.dispatchEvent(new CustomEvent('daop:vicino', { detail: d }));
        } catch (e) { /* browser antichi: il filtro funziona lo stesso */ }
      }

      /* Una voce senza coordinate non e' "lontana", e' sconosciuta: con un
         raggio attivo resta fuori, perche' dire "e' a 5 km" senza saperlo e'
         peggio che non mostrarla. */
      function entro(voce) {
        if (!centro || raggio === null) return true;
        var d = dist.get(voce);
        return d !== undefined && d <= raggio;
      }

      function attivo() { return !!centro && raggio !== null; }

      function impostaCentro(la, lo, etichetta, metodo) {
        /* Scrivere un comune nel campo scatena `input` e poi `change`, cioe'
           due volte lo stesso centro: senza questo si ricalcolavano le distanze
           di tutte le voci due volte e partiva un evento doppio. */
        if (centro && centro.la === la && centro.lo === lo) return;
        centro = { la: la, lo: lo };
        dist.clear();
        voci.forEach(function (v) {
          var d = distanza(la, lo, parseFloat(v.getAttribute('data-lat')),
            parseFloat(v.getAttribute('data-lon')));
          dist.set(v, d);
          var dove = opz.riga ? opz.riga(v) : null;
          if (!dove) return;
          var tag = v.querySelector('.ev-km');
          if (!tag) {
            tag = document.createElement('span');
            tag.className = 'ev-km';
            dove.appendChild(tag);
          }
          tag.textContent = ' · a ' + scriviKm(d);
        });
        if (opz.alRitocco) opz.alRitocco();
        var ordinate = [];
        dist.forEach(function (d) { ordinate.push(d); });
        raggio = null;
        for (var i = 0; i < STEPS.length && raggio === null; i++) {
          var n = 0;
          for (var j = 0; j < ordinate.length; j++) { if (ordinate[j] <= STEPS[i]) n++; }
          if (n >= SOGLIA_PARTENZA) raggio = STEPS[i];
        }
        if (raggio === null) raggio = STEPS[STEPS.length - 1];
        da.textContent = 'da ' + etichetta;
        da.hidden = false;
        azzera.hidden = false;
        /* Il campo del comune NON si chiude qui: la ricerca e' viva, e chi sta
           ancora battendo "novi" ha gia' un centro su un prefisso. Chiudergli
           il campo sotto le dita lo lascerebbe con un comune che non ha scelto
           e senza il modo di correggerlo. */
        if (go) go.hidden = true;
        nota.textContent = 'Distanze in linea d\'aria. La posizione resta nel tuo browser: non la inviamo a nessuno.';
        segnala(metodo);
        alCambio();
      }

      function togliCentro(tieniAperto) {
        centro = null; raggio = null; dist.clear();
        voci.forEach(function (v) {
          var t = v.querySelector('.ev-km');
          if (t) t.parentNode.removeChild(t);
        });
        if (opz.alRitocco) opz.alRitocco();
        da.hidden = true;
        azzera.hidden = true;
        chips.textContent = '';
        hint.textContent = '';
        if (!tieniAperto) {
          campo.hidden = true; campo.value = '';
          if (alt) alt.hidden = false;
        }
        if (go) { go.hidden = !gpsUsabile; go.disabled = false; go.textContent = '📍 Vicino a me'; }
        nota.textContent = '';
        alCambio();
      }

      /* Un gradino vuoto resta visibile ma spento: dice che li' non c'e'
         niente, che e' una risposta, invece di sparire e far ballare la barra. */
      function disegnaChip(per) {
        STEPS.forEach(function (s, i) {
          var b = chips.children[i];
          if (!b) {
            b = document.createElement('button');
            b.type = 'button';
            b.className = 'ev-geo-chip';
            b.addEventListener('click', function () {
              raggio = s;
              segnala('gradino');
              alCambio();
            });
            chips.appendChild(b);
          }
          b.textContent = s + ' km (' + per[i] + ')';
          b.disabled = per[i] === 0;
          b.setAttribute('aria-pressed', String(raggio === s));
        });
      }

      /* La pagina passa il predicato dei SUOI filtri: i conteggi dei gradini
         devono dire quanti eventi si vedrebbero davvero, non quanti ce ne sono
         in totale a quella distanza. */
      function conta(passaAltri) {
        if (!centro) { chips.textContent = ''; hint.textContent = ''; return; }
        var per = STEPS.map(function () { return 0; });
        var dentro = 0;
        voci.forEach(function (v) {
          if (passaAltri && !passaAltri(v)) return;
          var d = dist.get(v);
          if (d === undefined) return;
          STEPS.forEach(function (s, i) { if (d <= s) per[i]++; });
          if (d <= raggio) dentro++;
        });
        disegnaChip(per);
        /* A zero risultati si dice dove guardare. E' il difetto tipico dei
           filtri per distanza nelle zone rade, e l'unica correzione e' non
           lasciare il vuoto: da Cuneo entro 10 km ci sono 4 eventi, entro 30
           quaranta. */
        var prossimo = -1;
        for (var i = 0; i < STEPS.length; i++) {
          if (STEPS[i] > raggio && per[i] > 0) { prossimo = i; break; }
        }
        hint.textContent = (dentro === 0 && prossimo >= 0)
          ? 'Niente entro ' + raggio + ' km. Entro ' + STEPS[prossimo] + ' km ' +
            (per[prossimo] === 1 ? 'c\'è 1 evento.' : 'ce ne sono ' + per[prossimo] + '.')
          : '';
      }

      /* L'elenco dei comuni si ricava dalle voci alla prima apertura: un
         <datalist> generato sarebbe HTML in pagina per tutti e utile a pochi.
         Il punto di un comune e' la media dei suoi eventi - per una misura in
         linea d'aria basta e avanza. */
      function elencoComuni() {
        if (comuni) return comuni;
        var m = new Map();
        voci.forEach(function (v) {
          var n = v.getAttribute('data-citta');
          if (!n) return;
          var k = norm(n);
          if (!m.has(k)) m.set(k, { nome: n, la: 0, lo: 0, n: 0, k: k });
          var o = m.get(k);
          o.la += parseFloat(v.getAttribute('data-lat'));
          o.lo += parseFloat(v.getAttribute('data-lon'));
          o.n++;
        });
        comuni = [];
        m.forEach(function (o) {
          comuni.push({ nome: o.nome, la: o.la / o.n, lo: o.lo / o.n, k: o.k });
        });
        comuni.sort(function (a, b) { return a.nome.localeCompare(b.nome, 'it'); });
        comuni.forEach(function (c) {
          var o = document.createElement('option');
          o.value = c.nome;
          lista.appendChild(o);
        });
        return comuni;
      }

      function apriComune() {
        elencoComuni();
        campo.hidden = false;
        if (alt) alt.hidden = true;
        campo.focus();
      }

      function provaComune() {
        var t = norm(campo.value);
        /* Svuotare il campo e' il modo naturale di disdire: lasciare "da Novi
           Ligure" acceso sopra una casella vuota e' uno stato che non si
           spiega. */
        if (!t) { if (centro) togliCentro(true); return; }
        var l = elencoComuni(), hit = null, i;
        for (i = 0; i < l.length && !hit; i++) { if (l[i].k === t) hit = l[i]; }
        if (!hit && t.length >= 3) {
          for (i = 0; i < l.length && !hit; i++) { if (l[i].k.indexOf(t) === 0) hit = l[i]; }
          for (i = 0; i < l.length && !hit; i++) { if (l[i].k.indexOf(t) > -1) hit = l[i]; }
        }
        if (hit) { impostaCentro(hit.la, hit.lo, hit.nome, 'comune'); return; }
        /* Il catalogo dei comuni e' quello della pagina, non l'anagrafe: un
           paese senza eventi in programma semplicemente non c'e'. Dirlo, invece
           di lasciare la casella muta, e' la differenza fra una risposta e un
           guasto. */
        if (t.length >= 3) {
          if (centro) togliCentro(true);
          nota.textContent = 'Nessun evento in agenda a «' + campo.value.trim() +
            '». Prova un comune vicino.';
        }
      }

      function riposa() {
        go.disabled = false;
        go.textContent = '📍 Vicino a me';
      }

      function chiediPosizione() {
        var mio = ++richiesta;
        go.disabled = true;
        go.textContent = '📍 Cerco…';
        nota.textContent = '';
        /* La sveglia e' nostra ed e' necessaria: il `timeout` della Geolocation
           API misura solo il tempo per AGGANCIARE la posizione, non l'attesa
           del permesso. Se l'avviso del browser resta li' senza risposta - che
           e' il caso piu' comune, non un caso limite - non arriva ne' successo
           ne' errore, e il bottone resterebbe "Cerco…" per sempre. Provato. */
        var sveglia = setTimeout(function () {
          if (mio !== richiesta || centro) return;
          riposa();
          nota.textContent = 'Non abbiamo ancora la posizione. Intanto puoi scegliere un comune da cui partire.';
          apriComune();
        }, 10000);
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            clearTimeout(sveglia);
            /* Un "consenti" arrivato tardi vale lo stesso: la risposta buona
               non si butta perche' la sveglia era gia' suonata. */
            if (mio === richiesta) {
              impostaCentro(pos.coords.latitude, pos.coords.longitude, 'dove sei', 'gps');
            }
          },
          function (err) {
            clearTimeout(sveglia);
            if (mio !== richiesta) return;
            riposa();
            nota.textContent = (err && err.code === 1)
              ? 'Non abbiamo la tua posizione. Puoi scegliere un comune da cui partire.'
              : 'Non siamo riusciti a trovare la posizione. Puoi scegliere un comune da cui partire.';
            apriComune();
          },
          /* enableHighAccuracy resta false: il gradino piu' stretto e' 10 km,
             quindi un aggancio GPS non aggiunge niente e costa attesa e
             batteria. E una posizione di cinque minuti fa va benissimo: le
             sagre non si spostano. */
          { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 });
      }

      var gpsUsabile = !!(navigator.geolocation && window.isSecureContext);
      if (go) {
        go.hidden = !gpsUsabile;
        go.addEventListener('click', chiediPosizione);
      }
      if (alt) alt.addEventListener('click', apriComune);
      azzera.addEventListener('click', function () { togliCentro(false); });
      campo.addEventListener('change', provaComune);
      campo.addEventListener('input', provaComune);
      nodo.hidden = false;

      /* Se il permesso e' gia' stato negato il bottone non serve: chiederlo di
         nuovo non riapre nessun avviso, il browser rifiuta e basta. Meglio
         portare subito al ripiego che offrire un comando che non fa niente. */
      if (go && navigator.permissions && navigator.permissions.query) {
        navigator.permissions.query({ name: 'geolocation' }).then(function (p) {
          if (p.state === 'denied' && !centro) { gpsUsabile = false; go.hidden = true; }
        }).catch(function () {});
      }

      return { entro: entro, attivo: attivo, conta: conta };
    }
  };
})();
