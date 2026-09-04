// LE DOMANDE FREQUENTI — il markup segue il visibile, e le risposte non sono
// la stessa risposta.
//
// COSA DIFENDE, e sono due cose diverse.
//
// 1) FAQPage dichiarato E visibile, nei due versi. E' la violazione tipica di
//    questo markup e l'unica che si paga con un'azione manuale: dichiarare a
//    Google sette domande che in pagina non ci sono. Il generatore lo rende
//    impossibile per costruzione — faq_blocco() costruisce HTML e JSON-LD da
//    una lista sola — ma "per costruzione" e' vero finche' qualcuno non scrive
//    il secondo posto, ed e' esattamente il guasto ripetuto quindici volte in
//    questo repo (il footer, i marker delle rubriche, le stagionali). La prova
//    confronta i due elenchi invece di fidarsi.
//
// 2) LE RISPOSTE NON SONO BOILERPLATE. E' il rischio vero di questo blocco:
//    24 pagine comune con la stessa risposta sono contenuto sottile su un
//    sito che pubblica centinaia di pagine su template, cioe' la riga
//    "Scansionata, ma non indicizzata" del rapporto Indicizzazione — oggi 10
//    pagine su 131, un giudizio buono che queste FAQ possono rovinare. La
//    prova chiede che due pagine della stessa famiglia non abbiano lo stesso
//    blocco, che e' il modo piu' economico di accorgersene.
//
// QUELLO CHE NON PRETENDE, per non marcire: non conta le pagine con le FAQ,
// non conta le domande per pagina, non nomina un comune. Sono tutti numeri che
// cambiano ogni notte quando una sagra finisce — l'inciampo gia' pagato sei
// volte qui dentro. Si controlla il RAPPORTO fra due elenchi e la DIVERSITA'
// fra due pagine, che non hanno una taglia giusta.
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { esito, RADICE } = require('./_aiuto');

const FUORI = ['.git', 'tests', 'scripts', 'contenuti', 'data', 'assets', 'node_modules',
  // Le pagine di PROVA non sono il sito: corsi-prova.html e' noindex apposta e
  // prova_corsi.py le toglie i dati strutturati di proposito (una scheda
  // inventata dichiarata a Google sarebbe il danno che quella pagina esiste
  // per evitare). Pretendere qui le regole delle pagine vere vorrebbe dire
  // pretendere che smetta di essere una prova.
  'corsi-prova', 'corsi-prova.html'];

function pagine(dir = path.join(RADICE), base = '') {
  const out = [];
  for (const voce of fs.readdirSync(dir, { withFileTypes: true })) {
    if (FUORI.includes(voce.name)) continue;
    const rel = base ? `${base}/${voce.name}` : voce.name;
    if (voce.isDirectory()) out.push(...pagine(path.join(dir, voce.name), rel));
    else if (voce.name.endsWith('.html')) out.push(rel);
  }
  return out;
}

// Il testo di un frammento HTML come lo confronta un motore: senza tag, senza
// entita', senza spazi doppi. E' la stessa normalizzazione che fa _faq_testo()
// in genera_eventi.py — e va tenuta uguale, se no la prova bocciarebbe una
// coppia identica per una virgola di codifica.
const pulisci = (h) => h
  .replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&')
  .replace(/&#x27;/g, "'").replace(/&quot;/g, '"')
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
  .replace(/\s+/g, ' ')
  .trim();

// Il corpo della pagina SENZA i blocchi JSON-LD: e' quello che una persona
// legge, ed e' dove una domanda dichiarata deve comparire. Cercarla nell'HTML
// intero non proverebbe niente — ci sta gia', dentro il markup.
const corpoDi = (html) => pulisci(
  html.replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>/g, ' '));

// Le domande del NOSTRO blocco: il testo dei <summary> dentro .faq.
// Torna null sulle pagine che le FAQ le hanno scritte a mano con un altro
// markup — ginetto.html e piattosano.html usano .faq-list/.faq-item,
// metodo.html le scrive come titoli. Quelle passano dal verso A qui sotto, che
// non guarda i tag: cosi' la prova non obbliga il sito ad avere una sola
// grafia per una cosa che ne ha tre da prima che questo blocco esistesse.
function domandeNostre(html) {
  const blocco = html.match(/<section class="faq"[\s\S]*?<\/section>/);
  if (!blocco) return null;
  return [...blocco[0].matchAll(/<summary>([\s\S]*?)<\/summary>/g)].map((m) => pulisci(m[1]));
}

// Le domande DICHIARATE: i Question dentro un FAQPage, in qualunque blocco
// JSON-LD della pagina.
function domandeInMarkup(html) {
  const out = [];
  for (const m of html.matchAll(
    /<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)) {
    let dati;
    try { dati = JSON.parse(m[1]); } catch (e) { return { rotto: true, voci: out }; }
    const nodi = dati['@graph'] || [dati];
    for (const n of nodi) {
      if (n && n['@type'] === 'FAQPage') {
        for (const q of n.mainEntity || []) out.push(pulisci(String(q.name || '')));
      }
    }
  }
  return { rotto: false, voci: out };
}

// La famiglia di una pagina, per il confronto anti-boilerplate: le pagine
// comune fra loro, le sagre-provincia fra loro, e cosi' via. Confrontare una
// pagina comune con corsi.html non direbbe niente.
function famiglia(rel) {
  if (rel.startsWith('eventi/comune/')) return 'pagine comune';
  if (/^sagre-provincia-/.test(rel)) return 'sagre provinciali';
  if (/^eventi\/(oggi|weekend)-provincia-/.test(rel)) return "pagine d'incrocio";
  return null;
}

module.exports = async function () {
  const st = esito();
  st.titolo('Domande frequenti — il markup segue il visibile');

  const tutte = pagine();
  const conFaq = [];
  const invisibili = [];
  const nonDichiarate = [];
  const jsonRotto = [];
  let dichiaranti = 0;

  for (const rel of tutte) {
    const html = fs.readFileSync(path.join(RADICE, rel), 'utf8');
    const { rotto, voci: dichiarate } = domandeInMarkup(html);
    if (rotto) { jsonRotto.push(rel); continue; }
    const nostre = domandeNostre(html);
    if (!nostre && !dichiarate.length) continue;

    // VERSO A, e vale su QUALUNQUE grafia: se lo diciamo a Google, deve
    // esserci per chi legge. E' la violazione che si paga con un'azione
    // manuale, ed e' l'unica delle due che non dipende da come e' fatto
    // l'HTML: si cerca il testo della domanda nel corpo, non un tag.
    if (dichiarate.length) {
      dichiaranti++;
      const corpo = corpoDi(html);
      const fuori = dichiarate.filter((q) => !corpo.includes(q));
      if (fuori.length) invisibili.push(`${rel} — ${fuori.slice(0, 2).join(' / ')}`);
    }

    // VERSO B, sul blocco che generiamo noi: quello che si vede e' dichiarato,
    // nello stesso ordine e senza ripetizioni. Il confronto e' su una lista e
    // non su un insieme apposta — una domanda dichiarata due volte e' un
    // errore di validazione vero, e come insieme passerebbe.
    if (nostre) {
      conFaq.push({ rel, html, quante: nostre.length });
      if (JSON.stringify(nostre) !== JSON.stringify(dichiarate)) {
        nonDichiarate.push(`${rel} (${nostre.length} in pagina, ${dichiarate.length} nel markup)`);
      }
    }
  }

  st.ok(jsonRotto.length === 0,
    'ogni blocco JSON-LD si legge' + (jsonRotto.length ? ` — ${jsonRotto.join(', ')}` : ''));

  st.ok(invisibili.length === 0,
    `ogni domanda dichiarata a Google è visibile in pagina (${dichiaranti} pagine)`
    + (invisibili.length ? ` — ${invisibili.join('; ')}` : ''));

  st.ok(nonDichiarate.length === 0,
    'nel blocco generato, quello che si vede è esattamente quello che si dichiara'
    + (nonDichiarate.length ? ` — ${nonDichiarate.join('; ')}` : ''));

  st.ok(conFaq.length > 0, `${conFaq.length} pagine hanno il blocco FAQ generato`);

  // Nessuna FAQ su una pagina che abbiamo tolto dall'indice: li' il blocco
  // sarebbe contenuto sottile su una pagina che il noindex sta gia' tenendo
  // fuori proprio perche' non ha niente da dire.
  const suNoindex = conFaq.filter(({ html }) =>
    /<meta\s+name="robots"\s+content="[^"]*noindex/i.test(html.slice(0, 6000)));
  st.ok(suNoindex.length === 0,
    'nessun blocco FAQ su una pagina noindex'
    + (suNoindex.length ? ` — ${suNoindex.map((p) => p.rel).join(', ')}` : ''));

  // ANTI-BOILERPLATE. Due pagine della stessa famiglia non possono avere lo
  // stesso identico blocco: se succede, le risposte hanno smesso di usare i
  // dati della pagina e sono tornate a essere un testo fisso.
  const perFamiglia = new Map();
  for (const { rel, html } of conFaq) {
    const fam = famiglia(rel);
    if (!fam) continue;
    const blocco = html.match(/<section class="faq"[\s\S]*?<\/section>/);
    if (!blocco) continue;
    // L'impronta si prende sulle DOMANDE E RISPOSTE, non sul blocco intero:
    // l'occhiello sotto il titolo nomina il comune ("Le risposte usano i numeri
    // a Cuneo"), quindi da solo basta a rendere unico anche un blocco di sette
    // risposte identiche. Verificato rimettendo il difetto il 03/09/2026: con
    // l'impronta sul blocco intero la prova restava VERDE mentre le ventiquattro
    // pagine dicevano tutte la stessa cosa. Una prova che non vede il difetto
    // che esiste per vedere e' peggio di nessuna prova.
    const contenuto = blocco[0]
      .replace(/<p class="faq-sub">[\s\S]*?<\/p>/, '')
      .replace(/<h2 class="faq-t"[\s\S]*?<\/h2>/, '');
    const impronta = crypto.createHash('md5').update(pulisci(contenuto)).digest('hex');
    if (!perFamiglia.has(fam)) perFamiglia.set(fam, new Map());
    const m = perFamiglia.get(fam);
    m.set(impronta, [...(m.get(impronta) || []), rel]);
  }
  for (const [fam, m] of perFamiglia) {
    const gemelle = [...m.values()].filter((v) => v.length > 1);
    st.ok(gemelle.length === 0,
      `${fam}: ${m.size} blocchi distinti su ${[...m.values()].flat().length} pagine`
      + (gemelle.length ? ` — identiche: ${gemelle.map((g) => g.join(' = ')).join('; ')}` : ''));
  }

  // Non e' un'asserzione: e' il numero che rende leggibile il verde.
  const domande = conFaq.reduce((n, p) => n + p.quante, 0);
  console.log(`  --   ${conFaq.length} pagine con FAQ, ${domande} domande in tutto`);

  return st;
};
