// I profili social: si compongono da PROVINCE_IG, e si possono toccare.
//
// PERCHE' ESISTE. Il footer e' l'unico pezzo del guscio che nessun generatore
// compone: _guscio() lo COPIA da eventi.html e lo incolla in ~470 pagine.
// Finche' una cosa si copia e basta, l'unico posto che la sa e' quello scritto
// a mano - ed e' costato @daop_cuneo mancante da TUTTO il sito, con il codice
// che lo sapeva (sta in PROVINCE_IG, col curatore accanto) e il footer no.
// Quel difetto non lo prendeva nessuna rete di sicurezza, perche' non era un
// file rimasto indietro: era un file che nessuno aveva mai avuto il compito di
// aggiornare.
//
// Le prove qui sotto guardano RAPPORTI fra insiemi e mai conteggi. "Sei link
// nel footer" sarebbe rosso il giorno che apre la quarta provincia, cioe'
// quando il sito fa la cosa giusta: e' l'inciampo gia' pagato piu' volte in
// questo repo (la copertura delle coordinate, il conteggio delle quattro
// porte, il robots delle pagine realta').
'use strict';

const fs = require('fs');
const path = require('path');
const { apri, esito, RADICE } = require('./_aiuto');

function leggi(f) {
  return fs.readFileSync(path.join(RADICE, f), 'utf8');
}

// Le province e i loro profili si leggono dal GENERATORE, che e' l'unico posto
// dove vivono. Non e' "la prova che chiama il codice che deve giudicare": qui
// si legge il DATO (la mappa), non la funzione che compone la voce. Il
// confronto resta fra due cose indipendenti - quello che la mappa dice e
// quello che le pagine stampano - ed e' esattamente il buco che @daop_cuneo ha
// attraversato.
function profiliAttesi() {
  const src = leggi('scripts/genera_eventi.py');
  const pubbl = (src.match(/^PROVINCE_PUBBLICATE\s*=\s*\(([^)]*)\)/m) || [])[1] || '';
  const sigle = [...pubbl.matchAll(/'([A-Z]{2})'/g)].map((m) => m[1]);
  const mappa = (src.match(/^PROVINCE_IG\s*=\s*\{([\s\S]*?)^\}/m) || [])[1] || '';
  const voci = [];
  for (const sigla of sigle) {
    const blocco = (mappa.match(
      new RegExp(`'${sigla}':\\s*\\{([\\s\\S]*?)\\},?\\s*(?='[A-Z]{2}':|$)`)) || [])[1];
    if (!blocco) continue;
    const ig = (blocco.match(/'ig':\s*'([^']+)'/) || [])[1];
    const fb = (blocco.match(/'fb':\s*'([^']+)'/) || [])[1] || null;
    if (ig) voci.push({ sigla, ig, fb });
  }
  return voci;
}

// Le pagine sono una per famiglia, non un elenco lungo: quello che si prova e'
// che il guscio arrivi dappertutto, e una per specie basta a dirlo. Le famiglie
// sono quelle che ricevono il footer per tre strade diverse - a mano
// (aggiorna_nav), da _guscio(), e dal guscio SUO di genera_rubriche.py, che e'
// gia' due volte la fonte dello stesso difetto sui marker.
function campione() {
  const fissi = ['eventi.html', 'index.html', 'rubriche.html', '404.html',
    'luoghi.html', 'sagre-provincia-cuneo.html', 'eventi-provincia-cuneo.html'];
  const uno = (dir) => {
    const d = path.join(RADICE, dir);
    if (!fs.existsSync(d)) return [];
    const f = fs.readdirSync(d)
      .filter((x) => x.endsWith('.html') && !x.startsWith('box-')).sort()[0];
    return f ? [dir + '/' + f] : [];
  };
  return [...fissi.filter((f) => fs.existsSync(path.join(RADICE, f))),
    ...uno('eventi'), ...uno('eventi/comune'), ...uno('rubriche'), ...uno('idee')];
}

// Il contrasto si MISURA nel reso, non si legge nel CSS. E' la classe di guasto
// del crumb dei corsi a 1,07:1 e della barra delle azioni alta 915px: HTML
// giusto, CSS che a leggerlo sembra a posto, e nessuno che se ne accorge.
// L'alfa del colore si fonde col primo sfondo opaco che si incontra risalendo.
const MISURA_CONTRASTO = (sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const num = (s) => (s.match(/[\d.]+/g) || []).map(Number);
  const lum = (c) => {
    const [r, g, b] = c.map((v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  let n = el;
  let sfondo = [255, 255, 255];
  while (n) {
    const p = num(getComputedStyle(n).backgroundColor);
    if ((p.length > 3 ? p[3] : 1) > 0.99) { sfondo = p.slice(0, 3); break; }
    n = n.parentElement;
  }
  const f = num(getComputedStyle(el).color);
  const a = f.length > 3 ? f[3] : 1;
  const fg = f.slice(0, 3).map((v, i) => v * a + sfondo[i] * (1 - a));
  const L1 = lum(fg);
  const L2 = lum(sfondo);
  return (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
};

module.exports = async function (browser) {
  const r = esito();
  const attesi = profiliAttesi();
  const pagine = campione();

  r.titolo('I profili social — la colonna si compone da PROVINCE_IG');
  r.ok(attesi.length >= 1,
    `PROVINCE_IG dichiara ${attesi.length} province pubblicate con un profilo`);

  // L'INVARIANTE: ogni provincia che ha un profilo nel codice ce l'ha nel
  // footer di ogni pagina. Non "sei link": una provincia nuova entra da sola e
  // questa prova continua a valere senza che nessuno la tocchi.
  //
  // Si guarda DENTRO il <footer>, non la pagina intera, e non e' pignoleria:
  // scritta sulla pagina intera questa prova passava anche col difetto rimesso,
  // perche' eventi.html nomina @daop_cuneo anche nel blocco .ev-fonti e le
  // schede lo nominano nel credito. Cercare una stringa "da qualche parte" e'
  // il modo in cui una prova si autoconvince: la colonna poteva essere vuota e
  // lei diceva di si'. Trovato rimettendo il difetto, non ragionandoci sopra.
  for (const f of pagine) {
    const foot = (leggi(f).match(/<footer[\s\S]*?<\/footer>/) || [''])[0];
    const manca = attesi.filter((p) => !foot.includes('instagram.com/' + p.ig));
    r.ok(foot !== '' && manca.length === 0, foot === ''
      ? `${f}: non ha un <footer>`
      : manca.length
        ? `${f}: nel footer manca il profilo di ${manca.map((p) => '@' + p.ig).join(', ')}`
        : `${f}: tutte e ${attesi.length} le pagine di provincia sono nel footer`);
  }

  // Il verso opposto: un profilo in pagina che nel codice non esiste piu' e'
  // un link a una pagina che potrebbe essere stata chiusa. Si guarda solo la
  // colonna del footer, perche' altrove (il credito, le rubriche) gli handle
  // possono essere di terzi.
  const noti = new Set(attesi.map((p) => p.ig));
  for (const f of ['eventi.html', 'index.html']) {
    const col = (leggi(f).match(
      /FOOTER-SOCIAL:START -->([\s\S]*?)<!-- FOOTER-SOCIAL:END/) || [])[1] || '';
    const estranei = [...col.matchAll(/instagram\.com\/([^/"']+)/g)]
      .map((m) => m[1]).filter((h) => !noti.has(h));
    r.ok(col !== '' && estranei.length === 0, col === ''
      ? `${f}: il blocco FOOTER-SOCIAL non c'è più, la colonna è tornata scritta a mano`
      : estranei.length
        ? `${f}: nel footer c'è @${estranei.join(', @')}, che PROVINCE_IG non conosce`
        : `${f}: nessun profilo nel footer che il codice non conosca`);
  }

  // I marker del guscio non devono sopravvivere in una pagina generata. E' il
  // difetto gia' preso DUE volte da tests/porte.js - coi centri e poi identico
  // coi corsi - e il terzo marker e' questo.
  for (const f of pagine.filter((x) => x.includes('/'))) {
    r.ok(!/<!-- [A-Z][A-Z0-9-]*:(?:START|END) -->/.test(leggi(f)),
      `${f}: nessun marker del guscio è finito in pagina`);
  }

  r.titolo('Il footer si legge — contrasto misurato nel reso');

  // SI MISURA SU DUE FAMIGLIE, e la ragione e' il difetto che questa prova ha
  // avuto nascendo. Lo stesso footer si rende con DUE contrasti diversi:
  //
  //   eventi.html        <style> a riga 50, il link al system CSS a riga 537
  //   pagine generate    il link a riga 26, poi il <style> copiato da _guscio()
  //
  // Le due regole hanno la stessa specificita' (una classe), quindi decide
  // l'ordine - e l'ordine e' invertito fra le due famiglie. Il system CSS dice
  // 0.58/0.60, lo <style> diceva 0.3/0.5: su eventi.html vinceva il primo e la
  // pagina era leggibile, sulle ~570 generate vinceva il secondo. Il difetto
  // stava dove sta il 77% del traffico, e la pagina che uno guarda per prima
  // era l'unica sana. Misurando solo eventi.html questa prova sarebbe rimasta
  // verde per tutto il tempo in cui il sito era rotto: verificato rimettendo
  // il difetto, non dedotto.
  const scheda = fs.readdirSync(path.join(RADICE, 'eventi'))
    .filter((f) => f.endsWith('.html') && !f.startsWith('box-'))
    .map((f) => 'eventi/' + f)
    .find((f) => leggi(f).includes('class="ev-fonte"'));

  for (const f of ['eventi.html', scheda].filter(Boolean)) {
    const { ctx, page } = await apri(browser, f, 360);
    for (const [sel, che] of [['.footer-col-title', 'titolo di colonna'],
      ['.footer-col-links a', 'link del footer']]) {
      const c = await page.evaluate(MISURA_CONTRASTO, sel);
      r.ok(c !== null && c >= 4.5,
        `${f} — ${che}: ${c === null ? 'elemento assente' : c.toFixed(2) + ':1'} (minimo AA 4,5:1)`);
    }
    // La colonna e' cresciuta: "Instagram Alessandria" invece di "Instagram
    // AL". La sigla chiede a chi legge di sapere il codice della propria
    // provincia; il nome no. Il prezzo si paga in larghezza, sul telefono.
    const largo = await page.evaluate(() =>
      document.documentElement.scrollWidth > window.innerWidth);
    r.ok(!largo, `${f}: a 360px la colonna più lunga non fa scorrere la pagina di lato`);
    await ctx.close();
  }

  r.titolo('Il credito si può toccare — e resta un credito');
  r.ok(!!scheda, scheda ? `cavia: ${scheda}` : 'nessuna scheda evento ha il credito');
  if (scheda) {
    const s2 = await apri(browser, scheda, 360);
    const m = await s2.page.evaluate(() => {
      const p = document.querySelector('.ev-fonte');
      const a = p && p.querySelector('.ev-ig');
      if (!a) return null;
      const rr = a.getBoundingClientRect();
      return {
        h: rr.height,
        testo: p.textContent.replace(/\s+/g, ' ').trim(),
        href: a.getAttribute('href'),
        quota: (rr.top + window.scrollY) / document.documentElement.scrollHeight,
      };
    });
    r.ok(m !== null, m ? 'la maniglia del credito esiste' : "la maniglia .ev-ig non c'è");
    if (m) {
      // 24px e' il minimo di WCAG 2.5.8. NON era una violazione prima - i link
      // in linea sono esentati - quindi questa e' una soglia di usabilita', non
      // di conformita': un handle di dieci caratteri alto 18px dentro un
      // paragrafo di testo piccolo si sbaglia col dito.
      r.ok(m.h >= 24, `la maniglia è alta ${Math.round(m.h)}px (minimo 24)`);
      // Il VERBO. Il credito diceva da dove viene l'evento e si fermava li':
      // un'attribuzione senza invito e senza ragione, cioe' una cosa che si
      // legge e non si tocca.
      r.ok(/seguila/i.test(m.testo),
        'il credito dice cosa si trova seguendo la pagina, non solo da dove viene');
      // UNA destinazione, non sei. La pagina sa gia' in che provincia si trova:
      // chiederlo a chi legge e' la domanda che il footer fa e questa no.
      const suoi = attesi.filter((p) => (m.href || '').includes(p.ig));
      r.ok(suoi.length === 1,
        `il credito porta a una pagina sola (${suoi.map((p) => '@' + p.ig).join(', ') || m.href})`);
      // E RESTA UN CREDITO. Dal 28/08/2026 Ginetto e' l'unica richiesta del
      // sito e il 04/09 il canale WhatsApp e' stato chiuso apposta per non
      // dividere l'attenzione: due richieste nello stesso punto si dimezzano, e
      // misurandole insieme non si saprebbe piu' quale ha mosso il numero.
      // Questa prova esiste perche' "facciamolo risaltare" e' esattamente la
      // proposta che tornera'.
      r.ok(m.quota > 0.5,
        `sta nella metà bassa della pagina (${Math.round(m.quota * 100)}%), non è una seconda richiesta in cima`);
    }
    await s2.ctx.close();
  }

  return r;
};
