// Le quattro porte: eventi, luoghi, centri, corsi.
//
// Cosa difende questa prova, e perche' e' nata. Fino al 20/08/2026 due famiglie
// su quattro non avevano una porta da nessuna parte — la nav ne aveva due
// (Eventi, Luoghi), il footer due DIVERSE (Eventi, Corsi) — e tre pagine
// ricevevano ZERO link dal corpo di qualunque altra pagina: centri-invernali,
// centri-pasquali e piscine stavano solo in sitemap. E' lo stesso guasto gia'
// diagnosticato e gia' risolto su luoghi.html il 14/08 ("alla nav non ci va
// nessuno"), che li' era costato tutto il traffico della pagina.
//
// Sono difetti che non fanno rumore: nessuna pagina si rompe, nessun
// generatore fallisce, e si vedono solo contando i link a mano. Per questo
// stanno in una prova e non in un commento.
'use strict';

const fs = require('fs');
const path = require('path');
const { apri, esito, RADICE } = require('./_aiuto');

// La famiglia, il suo hub, e la chiave che quell'hub NON deve linkare (se
// stesso). L'ordine e' quello della nav: prima "cosa si fa in una data", poi
// "dove si va", poi le due a iscrizione.
const HUB = [
  ['eventi', 'eventi.html', '/eventi.html'],
  ['luoghi', 'luoghi.html', '/luoghi.html'],
  ['centri', 'centri-estivi.html', '/centri-estivi.html'],
  ['corsi', 'corsi.html', '/corsi.html'],
];

// Le tre pagine che erano orfane. Il conteggio dei link entranti dice qualcosa
// SOLO perche' nav e footer non le nominano: se un giorno una di queste entra
// in nav, questa prova diventa verde per il motivo sbagliato e va rifatta
// guardando il corpo invece del file intero.
const EX_ORFANE = ['centri-invernali.html', 'centri-pasquali.html', 'piscine.html'];

function html(f) {
  return fs.readFileSync(path.join(RADICE, f), 'utf8');
}

// La stagione dei centri che ha diritto alla nav. La regola e' la stessa di
// genera_eventi.stagione_centri() e va tenuta identica: vince quella che sta
// per cominciare, e una gia' cominciata (data nel passato) passa davanti.
// Riscritta qui apposta: una prova che chiama il codice che deve giudicare non
// prova niente.
function stagioneViva() {
  let d;
  try { d = JSON.parse(html('data/centri-stagioni.json')); } catch (e) { return null; }
  const vive = Object.values(d).filter((v) => v && v.attivi && v.file && v.voce
    && fs.existsSync(path.join(RADICE, v.file)));
  if (!vive.length) return null;
  vive.sort((a, b) => (a.inizio === null) - (b.inizio === null)
    || String(a.inizio).localeCompare(String(b.inizio))
    || b.attivi - a.attivi
    || a.file.localeCompare(b.file));
  return vive[0];
}

// I tre file di stagione, per accorgersi che una nav ne nomina uno qualunque.
const FILE_CENTRI = ['centri-estivi.html', 'centri-invernali.html',
  'centri-pasquali.html'];

// I corsi hanno un interruttore (CORSI_IN_INDICE in genera_eventi.py): fuori
// indice la pagina resta online ma esce da nav, sitemap e riga delle quattro
// porte. Quindi da qui in avanti le porte sono TRE o QUATTRO, e una prova che
// ne pretende quattro sarebbe rossa proprio quando il sito fa la cosa giusta —
// e' lo stesso errore gia' corretto per la stagione dei centri.
//
// Lo stato non si legge dal generatore ne' da un file di appoggio: si legge da
// corsi.html, cioe' dal risultato. Cosi' quello che si controlla e' che il sito
// sia d'accordo con se stesso, che e' la domanda vera — un interruttore girato
// a meta' (noindex ma ancora in nav) e' esattamente il difetto che qui deve
// diventare rosso.
function corsiInIndice() {
  try {
    return /name="robots" content="index/.test(html('corsi.html'));
  } catch (e) {
    return false;
  }
}

// Tutti gli .html del repo, per contare i link entranti.
function tutte() {
  const out = [];
  (function giu(dir) {
    for (const v of fs.readdirSync(path.join(RADICE, dir), { withFileTypes: true })) {
      if (v.name === 'node_modules' || v.name === '.git') continue;
      const rel = dir ? path.join(dir, v.name) : v.name;
      if (v.isDirectory()) giu(rel);
      else if (v.name.endsWith('.html')) out.push(rel);
    }
  })('');
  return out;
}

module.exports = async function porte(browser) {
  const r = esito();
  r.titolo('Le quattro porte — la riga in coda ai quattro hub');

  const conteggi = JSON.parse(html('data/conteggi.json'));
  const corsiVivi = corsiInIndice();
  // Gli hub che partecipano alle porte. Un hub fuori indice non e' una porta:
  // ne' la propria ne' quella che le altre pagine gli aprono.
  const PORTE = HUB.filter(([k]) => k !== 'corsi' || corsiVivi);
  console.log(`  --   corsi ${corsiVivi ? 'in indice' : 'FUORI indice'}: `
    + `${PORTE.length} porte`);

  for (const [chiave, file, proprio] of HUB) {
    const s = html(file);
    const blocco = s.match(/<section class="eco[^"]*"[\s\S]*?<\/section>/);
    r.ok(!!blocco, blocco
      ? `${file}: la riga c'è`
      : `${file}: la riga delle quattro porte NON c'è`);
    if (!blocco) continue;
    // Una pagina che linka se stessa in una riga di "altre cose" e' un link
    // che non porta da nessuna parte, ed e' l'errore piu' facile da fare
    // passando la chiave sbagliata a blocco_ecosistema().
    r.ok(!blocco[0].includes(`href="${proprio}"`),
      `${file}: la riga non linka se stessa (${chiave})`);
    // Tante quante le porte vive, meno se stessa se e' una di quelle. Una
    // pagina fuori indice tiene la sua riga (serve a chi ci arriva da un link
    // girato) ma non compare in quelle degli altri.
    const attesi = PORTE.length - (PORTE.some(([k]) => k === chiave) ? 1 : 0);
    const card = (blocco[0].match(/class="eco-c"/g) || []).length;
    r.ok(card === attesi, card === attesi ? `${file}: ${card} card`
      : `${file}: ${card} card invece di ${attesi}`);
    // E soprattutto: una porta verso una pagina fuori indice non si apre.
    for (const [k, , href] of HUB) {
      if (PORTE.some(([kk]) => kk === k)) continue;
      r.ok(!blocco[0].includes(`href="${href}"`),
        `${file}: non apre la porta di ${k}, che è fuori indice`);
    }
  }

  // Sulla home non si e' dentro nessuna famiglia, quindi escono tutte e
  // quattro: e' il solo posto in cui la riga ne ha quattro.
  const home = html('index.html');
  const fascia = home.match(/<section class="eco eco--porte"[\s\S]*?<\/section>/);
  r.ok(!!fascia, fascia ? 'index.html: la fascia c\'è' : 'index.html: la fascia NON c\'è');
  if (fascia) {
    const card = (fascia[0].match(/class="eco-c"/g) || []).length;
    r.ok(card === PORTE.length, card === PORTE.length
      ? `index.html: ${card} porte`
      : `index.html: ${card} porte invece di ${PORTE.length}`);
    for (const [chiave, , proprio] of PORTE) {
      r.ok(fascia[0].includes(`href="${proprio}"`),
        `index.html: la fascia porta a ${chiave}`);
    }
  }

  r.titolo('Le quattro porte — il numero, non l\'etichetta');

  // "894 posti per famiglie" e' una ragione per toccare, "Luoghi" no: e' la
  // regola di link_luoghi(), e qui si controlla che il numero arrivi davvero
  // in pagina. Sotto MIN_CONTEGGIO (5) il generatore stampa apposta la riga
  // descrittiva invece del conteggio, quindi si guardano solo le famiglie che
  // stanno sopra soglia.
  // Quello che si controlla e' che in pagina ci sia UN NUMERO, non che sia
  // esattamente quello di data/conteggi.json oggi. Il registro e' in ritardo di
  // un giro per costruzione — dentro la stessa run genera_eventi gira prima di
  // genera_luoghi — quindi il confronto esatto rendeva questa prova rossa ogni
  // volta che un conteggio cambiava, cioe' quasi ogni notte: verificato il
  // 21/08/2026, conteggi.json a 830 luoghi ed eventi.html a 825, ed era il
  // comportamento giusto di tutti e due. Il disallineamento si stampa come
  // nota, perche' resta utile vederlo, ma non e' un difetto.
  const MIN = 5;
  const eventi = html('eventi.html');
  for (const [chiave, , proprio] of PORTE) {
    const n = conteggi[chiave] || 0;
    if (chiave === 'eventi' || n < MIN) continue;
    const card = eventi.match(new RegExp(
      `<a class="eco-c" href="${proprio}">.*?<span class="eco-d">([^<]*)</span>`));
    const stampato = card && card[1].match(/^(\d+) /);
    r.ok(!!stampato, stampato
      ? `eventi.html: il conteggio di ${chiave} è in pagina (${stampato[1]})`
      : `eventi.html: la card di ${chiave} non stampa un numero`);
    if (stampato && Number(stampato[1]) !== n) {
      console.log(`  --   ${chiave}: in pagina ${stampato[1]}, `
        + `nel registro ${n} (il ritardo di un giro, non un difetto)`);
    }
  }

  r.titolo('Le quattro porte — nessuna pagina resta orfana');

  const files = tutte();
  for (const orfana of EX_ORFANE) {
    // Il commento in cima a EX_ORFANE lo prevedeva: dal 21/08/2026 una di
    // queste PUO' stare in nav (la stagione viva), e allora contare i link
    // entranti misura la nav e non il corpo, cioe' la prova diventa verde per
    // il motivo sbagliato. Quella la salta: ce ne pensa la prova della nav.
    const in_nav = stagioneViva();
    if (in_nav && in_nav.file === orfana) {
      console.log(`  --   ${orfana}: è la stagione in nav, `
        + 'il conteggio dei link entranti non dice niente');
      continue;
    }
    const da = files.filter((f) => f !== orfana && html(f).includes(`/${orfana}`));
    r.ok(da.length > 0, da.length
      ? `${orfana}: ${da.length} pagine la linkano (es. ${da[0]})`
      : `${orfana}: ZERO link entranti, è tornata orfana`);
  }

  r.titolo('Le quattro porte — la nav e il cassetto del telefono');

  // La nav di eventi.html e' il guscio di ~350 pagine (_guscio la rilegge a
  // ogni run): se le porte sparissero da qui sparirebbero da tutto il sito.
  const nav = eventi.match(/<ul class="nav-links">[\s\S]*?<\/ul>/);
  r.ok(!!nav, nav ? 'eventi.html: la nav c\'è' : 'eventi.html: nav non trovata');
  const viva = stagioneViva();
  // Le porte come sono adesso: quella dei centri e' la stagione viva, e non
  // c'e' affatto se nessuna ha centri.
  const attese = PORTE.map(([chiave, f]) =>
    (chiave === 'centri' ? (viva ? viva.file : null) : f)).filter(Boolean);
  if (nav) {
    // La porta dei centri non e' un file fisso da qui in avanti: la decide il
    // foglio, e questa prova deve leggere la stessa fonte del generatore. Con
    // "centri-estivi.html" scritto a mano sarebbe diventata rossa a novembre
    // per il motivo sbagliato, cioe' proprio quando il sito fa la cosa giusta.
    const ordine = attese.map((f) => nav[0].indexOf(`href="${f}"`));
    r.ok(ordine.every((i) => i >= 0), viva
      ? `la nav porta tutte e quattro le porte (centri: ${viva.file})`
      : 'la nav porta le tre porte con contenuto (nessuna stagione di centri)');
    r.ok(ordine.every((v, i) => i === 0 || v > ordine[i - 1]),
      'e nell\'ordine giusto: eventi, luoghi, centri, corsi');
    // Fuori indice la voce non deve restare: sarebbe l'interruttore girato a
    // meta', cioe' un link in nav su ~360 pagine verso una pagina che stiamo
    // chiedendo a Google di non tenere.
    r.ok(nav[0].includes('href="corsi.html"') === corsiVivi,
      corsiVivi ? 'la nav porta i corsi'
        : 'la nav non nomina i corsi (fuori indice)');
    // Una stagione sola, e quella giusta. Senza stagioni vive non deve restare
    // un residuo: e' meta' del difetto da cui e' nato tutto questo — la nav
    // diceva "Centri estivi" anche a novembre, su ~360 pagine.
    const nominati = FILE_CENTRI.filter((f) => nav[0].includes(`href="${f}"`));
    r.ok(nominati.length === (viva ? 1 : 0), viva
      ? `la nav nomina una stagione sola: ${nominati.join(', ') || 'NESSUNA'}`
      : `nessun centro in nessuna stagione, e la nav non ne nomina (${nominati.length})`);
    // La nav a nove voci era gia' tagliata a destra sopra i 901px, che e' il
    // motivo per cui le porte non ci stavano: se qualcuno la riallunga, questa
    // prova lo dice prima dello screenshot.
    const voci = (nav[0].match(/<li>/g) || []).length;
    r.ok(voci <= 7, `nav di ${voci} voci: sopra le sette si taglia sul desktop`);
  }

  // Sul telefono il cassetto e' l'unica nav che esiste (il 90% del traffico):
  // li' non si toglie niente, si mette in ordine — le quattro porte davanti,
  // il resto sotto l'etichetta.
  const mob = eventi.match(/<div class="mobile-menu"[\s\S]*?\n<\/div>/);
  r.ok(!!mob, mob ? 'eventi.html: il cassetto c\'è' : 'cassetto del telefono non trovato');
  if (mob) {
    const sep = mob[0].indexOf('class="mm-sep"');
    r.ok(sep > 0, 'il cassetto separa le porte dal resto');
    // Con HUB fisso questa riga passava per il motivo sbagliato: cercando
    // "centri-estivi.html" in un cassetto che d'inverno dice invernali,
    // indexOf tornava -1 e -1 > sep e' falso, cioe' verde senza aver
    // controllato niente.
    const dopo = attese.filter((f) => mob[0].indexOf(`href="${f}"`) > sep);
    r.ok(dopo.length === 0, dopo.length
      ? `nel cassetto ${dopo.length} porte stanno sotto il separatore`
      : 'le quattro porte stanno tutte prima del separatore');
  }

  r.titolo('La voce dei centri — dodici pagine che nessuno rigenera');

  // Le ~19 pagine generate ricevono la nav da _guscio(), che la rilegge da
  // eventi.html a ogni run: quelle sono allineate per costruzione. Le altre
  // dodici (index, ginetto, libri, piattosano, media, rubriche, esploratore,
  // bollino, privacy, cookie-policy, 404) non le scrive nessun generatore, e
  // sono quelle che derivano: sei mesi dopo direbbero una stagione diversa dal
  // resto del sito e nessuno se ne accorgerebbe. Le tiene insieme
  // aggiorna_nav(), che riscrive dove trova il marker — quindi il set giusto da
  // controllare e' proprio "chi ha il marker".
  const conMarker = files.filter((f) => !f.includes(path.sep)
    && html(f).includes('NAV-CENTRI:START'));
  r.ok(conMarker.length >= 12,
    `${conMarker.length} pagine con il marker della voce centri`);
  const attesa = viva ? viva.file : null;
  // In 404.html la stessa voce si scrive con la barra davanti, e non e' una
  // deriva: quella pagina la serve GitHub Pages all'URL richiesto, quindi da
  // /eventi/... un href relativo la manderebbe a /eventi/centri-estivi.html.
  // La stagione dev'essere la stessa delle altre undici; a cambiare e' solo
  // la forma del percorso.
  const fuori = conMarker.filter((f) => {
    const nv = html(f).match(/<ul class="nav-links">[\s\S]*?\/ul>/);
    if (!nv) return true;
    const pre = f === '404.html' ? '/' : '';
    const nom = FILE_CENTRI.filter((c) => nv[0].includes(`href="${pre}${c}"`));
    return nom.length !== (attesa ? 1 : 0) || (attesa && nom[0] !== attesa);
  });
  r.ok(fuori.length === 0, fuori.length
    ? `${fuori.length} pagine con la stagione sbagliata in nav: ${fuori.join(', ')}`
    : `tutte e ${conMarker.length} d'accordo su ${attesa || 'nessuna stagione'}`);

  // Il marker deve restare fuori dalle pagine generate: _guscio() lo toglie
  // quando copia la nav, se no sono tre commenti in piu' su ~360 pagine.
  const conMarkerGenerate = files.filter((f) => f.includes(path.sep)
    && /NAV-(?:CENTRI|CORSI):START/.test(html(f)));
  r.ok(conMarkerGenerate.length === 0, conMarkerGenerate.length
    ? `${conMarkerGenerate.length} pagine generate si portano dietro il marker`
    : 'le pagine generate non si portano dietro i marker');

  // Una prova nel browser, perche' il resto e' lettura di file: la riga deve
  // essere davvero visibile e cliccabile, non solo presente nell'HTML. Una
  // regola di CSS sbagliata (un display:none ereditato, un contenitore a
  // altezza zero) non si vede leggendo il sorgente.
  const { ctx, page } = await apri(browser, 'corsi.html', 412);
  const card = page.locator('.eco .eco-c');
  r.ok(await card.count() === 3, 'corsi.html a 412px: tre card nel DOM');
  r.ok(await card.first().isVisible(), 'e la prima è visibile');
  const alto = await card.first().evaluate((el) => el.getBoundingClientRect().height);
  r.ok(alto >= 44, `l'area toccabile è alta ${Math.round(alto)}px (minimo 44)`);
  // Sotto i 700px le tre card vanno in pila: affiancate sarebbero tre colonne
  // da un centimetro.
  const x = await card.evaluateAll((els) =>
    els.map((e) => Math.round(e.getBoundingClientRect().left)));
  r.ok(new Set(x).size === 1, `sul telefono le card sono in pila (x: ${x.join(', ')})`);

  // 404.html e' l'unica pagina a mano che non viene servita dal proprio
  // indirizzo: GitHub Pages la restituisce all'URL richiesto, quindi da
  // /eventi/una-scheda-cancellata.html un href relativo punta a
  // /eventi/eventi.html e ogni via d'uscita e' rotta - proprio per chi ci
  // arriva dalle schede evento, che sono il 70% del traffico. Misurato in
  // produzione il 28/08/2026: tutta la nav rotta, e l'unico link vivo era
  // quello che portava fuori dal sito.
  const q404 = html('404.html');
  const relativi = [...q404.matchAll(/ (?:href|src)="([^"/#][^":]*)"/g)].map((m) => m[1]);
  r.ok(relativi.length === 0, relativi.length
    ? `404.html ha ${relativi.length} percorsi relativi: ${[...new Set(relativi)].slice(0, 4).join(', ')}`
    : 'in 404.html ogni percorso è assoluto: la nav regge da qualunque cartella');

  // La via d'uscita di una pagina di errore non puo' essere l'unico link che
  // porta via dal sito.
  r.ok(!/nav-cta[^>]*>\s*Gioca ora/.test(q404) && /nav-cta[^>]*>\s*Contatti/.test(q404),
    'la CTA della 404 è Contatti, non un rimando fuori dominio');

  await ctx.close();
  return r;
};
