// Le pagine di intenzione lette il giorno dopo.
//
// La run notturna parte con ore di ritardo (06:45-06:54 UTC a settembre 2026,
// verso le 9 in Italia), e fino a quel momento /eventi/oggi.html diceva
// "oggi, venerdi' 11 settembre" letto di sabato, con sotto "Domani" quello che
// era gia' oggi (12/09/2026). LANDING_SCADUTI_JS in genera_eventi.py corregge
// quello che si puo' correggere senza dati nuovi. Qui si sposta l'orologio
// della pagina e si confronta la pagina col file com'e' su disco.
//
// Nessun conteggio: sarebbe rosso la prima notte in cui l'agenda cambia.
'use strict';

const fs = require('fs');
const path = require('path');
const { apri, orologio, piuGiorni, RADICE } = require('./_aiuto');

function generata(file) {
  const html = fs.readFileSync(path.join(RADICE, file), 'utf8');
  const gen = (html.match(/<main id="contenuto" data-generata="(\d{4}-\d{2}-\d{2})"/) || [])[1];
  return { html, gen };
}

// Gira nella pagina: legge la pagina viva e, per confronto, il file com'era.
function leggi(a) {
  const d = new Date();
  const iso = (x) => x.getFullYear() + '-' + String(x.getMonth() + 1).padStart(2, '0') +
    '-' + String(x.getDate()).padStart(2, '0');
  const testo = (n) => (n && n.firstChild && n.firstChild.nodeType === 3 ? n.firstChild.nodeValue : '');
  const riga = (l) => {
    const go = l.querySelector('.com-go');
    return {
      href: go ? go.getAttribute('href') : '',
      nome: go ? go.textContent : '',
      citta: testo(l.querySelector('.com-luogo')).replace(/ \([A-Z]{2}\)$/, ''),
      start: l.dataset.start,
      end: l.dataset.end,
      etichetta: testo(l.querySelector('.com-d')).split(' · ')[0],
    };
  };
  const sezione = (doc, ruolo) => {
    const s = doc.querySelector(`.com-grp[data-ruolo="${ruolo}"]`);
    return s ? { nascosta: s.hidden, ordine: s.dataset.ordine || '',
                 righe: [...s.querySelectorAll('li[data-start]')].map(riga) } : null;
  };
  const prima = new DOMParser().parseFromString(a.html, 'text/html');
  return {
    oggi: iso(d),
    primaRuoli: ['oggi', 'domani', 'primi'].flatMap((x) => (sezione(prima, x) || { righe: [] }).righe),
    primaRighe: prima.querySelectorAll('.ev-wrap li[data-end]').length,
    sez: { oggi: sezione(document, 'oggi'), domani: sezione(document, 'domani'),
           primi: sezione(document, 'primi') },
    righe: [...document.querySelectorAll('.ev-wrap li[data-end]')].map(riga),
    scade: [...document.querySelectorAll('[data-scade]')].map((n) => ({
      scade: n.dataset.scade, nascosto: n.hidden, sezione: n.classList.contains('com-grp'),
    })),
    vuote: [...document.querySelectorAll('.ev-wrap .com-grp')]
      .filter((g) => g.querySelector('.com-ev') && !g.querySelector('.com-ev li')).length,
  };
}

// Le invarianti che valgono su ogni pagina letta il giorno g.
function comuni(r, st, g) {
  r.ok(st.oggi === g, `l'orologio della pagina segna ${st.oggi} (atteso ${g})`);
  const finite = st.righe.filter((x) => x.end < g);
  r.ok(finite.length === 0, finite.length
    ? `${finite.length} righe gia' finite restano: ${finite.slice(0, 3).map((x) => x.href).join(', ')}`
    : 'nessuna riga gia\' finita resta in pagina');
  const dopo = piuGiorni(g, 1);
  const attesa = (x) => (x.start < g ? 'in corso' : x.start === g ? 'oggi' : x.start === dopo ? 'domani' : null);
  const storte = st.righe.filter((x) => (attesa(x)
    ? x.etichetta !== attesa(x)
    : ['in corso', 'oggi', 'domani'].includes(x.etichetta)));
  r.ok(storte.length === 0, storte.length
    ? `${storte.length} righe dicono il giorno sbagliato: ${storte.slice(0, 2).map((x) => `"${x.etichetta}" su ${x.start}`).join(', ')}`
    : '"in corso", "oggi" e "domani" in riga sono di oggi, non di ieri');
  const scaduti = st.scade.filter((x) => x.scade < g);
  r.ok(scaduti.every((x) => !x.sezione && x.nascosto),
    'quello che dice una data passata non si vede (e le sezioni scadute non restano)');
  r.ok(st.scade.filter((x) => x.scade >= g).every((x) => !x.nascosto),
    'quello che vale ancora resta visibile');
  r.ok(st.vuote === 0, `nessuna sezione rimasta senza righe (${st.vuote})`);
}

async function provaOggiDopo(r, browser, file, conGuardia = false) {
  r.titolo(`${file} — letta il giorno dopo`);
  const { html, gen } = generata(file);
  r.ok(!!gen, `la pagina dice quando e' stata generata (${gen || 'manca data-generata'})`);
  if (!gen) return;
  const g = piuGiorni(gen, 1);
  let { ctx, page } = await apri(browser, file, 412, orologio(g));
  const st = await page.evaluate(leggi, { html });
  await ctx.close();
  comuni(r, st, g);

  const copre = (x, giorno) => x.start <= giorno && x.end >= giorno;
  const so = st.sez.oggi;
  const inOggi = so && !so.nascosta ? so.righe : [];
  const hrefOggi = inOggi.map((x) => x.href);
  // Tutto quello che il file aveva sotto oggi/domani/primi e che oggi e'
  // aperto deve stare sotto "In corso oggi": e' la riga "Domani" che di
  // mattina era gia' oggi.
  const attese = [...new Set(st.primaRuoli.filter((x) => copre(x, g)).map((x) => x.href))];
  const mancano = attese.filter((h) => !hrefOggi.includes(h));
  r.ok(mancano.length === 0, mancano.length
    ? `${mancano.length} righe aperte oggi non stanno sotto "In corso oggi": ${mancano.slice(0, 3).join(', ')}`
    : `tutto quello che e' aperto oggi sta sotto "In corso oggi" (${attese.length})`);
  r.ok(inOggi.every((x) => copre(x, g)), 'sotto "In corso oggi" c\'e\' solo quello che e\' aperto oggi');
  r.ok(new Set(hrefOggi).size === hrefOggi.length, 'e nessuna riga ci compare due volte');
  const dom = st.sez.domani;
  r.ok(!dom || dom.righe.every((x) => !copre(x, g)), '"Domani" non tiene righe che sono gia\' di oggi');
  const primi = st.sez.primi;
  r.ok(!primi || (inOggi.length === 0 && primi.righe.every((x) => x.start > g)),
    '"I primi in arrivo" solo se oggi non c\'e\' niente, e solo con righe future');
  if (inOggi.length > 1) {
    const chiave = so.ordine === 'data'
      ? (x) => [x.start, x.citta, x.nome]
      : (x) => [x.citta, x.nome];
    const cmp = (a, b) => {
      const ka = chiave(a), kb = chiave(b);
      for (let i = 0; i < ka.length; i++) {
        if (ka[i] < kb[i]) return -1;
        if (ka[i] > kb[i]) return 1;
      }
      return 0;
    };
    r.ok(inOggi.every((x, i) => i === 0 || cmp(inOggi[i - 1], x) <= 0),
      `"In corso oggi" resta nell'ordine del generatore (${so.ordine || 'nessuno'})`);
  }

  if (conGuardia) {
    // Oltre due giorni non si tocca niente: e' un orologio sbagliato o un
    // generatore fermo, e indovinare farebbe piu' danno.
    const lontano = piuGiorni(gen, 10);
    ({ ctx, page } = await apri(browser, file, 412, orologio(lontano)));
    const st2 = await page.evaluate(leggi, { html });
    await ctx.close();
    r.ok(st2.righe.length === st2.primaRighe && st2.scade.every((x) => !x.nascosto),
      `con l'orologio a ${lontano} la pagina resta com'e' (${st2.righe.length}/${st2.primaRighe} righe)`);
  }
}

async function provaWeekendDopo(r, browser, file) {
  r.titolo(`${file} — letta il giorno dopo`);
  const { html, gen } = generata(file);
  r.ok(!!gen, `la pagina dice quando e' stata generata (${gen || 'manca data-generata'})`);
  if (!gen) return;
  const fine = (html.match(/class="ev-when" data-scade="(\d{4}-\d{2}-\d{2})"/) || [])[1];
  r.ok(!!fine, `il sottotitolo dice fino a quando vale (${fine || 'manca data-scade'})`);
  if (!fine) return;

  // Il giorno dopo, se e' ancora lo stesso weekend: le date restano vere, e
  // la pagina e' quella che il generatore rifarebbe, meno le righe finite.
  const g1 = piuGiorni(gen, 1);
  if (g1 <= fine) {
    const { ctx, page } = await apri(browser, file, 412, orologio(g1));
    const st = await page.evaluate(leggi, { html });
    await ctx.close();
    comuni(r, st, g1);
    r.ok(st.scade.length > 0 && st.scade.every((x) => !x.nascosto),
      'ancora lo stesso weekend: sottotitolo, apertura e giorni restano');
  }

  // Il giorno dopo la domenica. Si prova solo se cade entro i due giorni in
  // cui il JS lavora - cioe' se la pagina e' stata generata nel weekend.
  const g = piuGiorni(fine, 1);
  if (g <= piuGiorni(gen, 2)) {
    const { ctx, page } = await apri(browser, file, 412, orologio(g));
    const st = await page.evaluate(leggi, { html });
    await ctx.close();
    comuni(r, st, g);
    r.ok(!st.scade.some((x) => x.sezione), 'i giorni del weekend passato non restano in pagina');
  } else {
    console.log(`  --   dopo il weekend (${g}) non si prova: la pagina e' del ${gen}, `
      + 'oltre i due giorni in cui il JS corregge');
  }
}

module.exports = { provaOggiDopo, provaWeekendDopo };
