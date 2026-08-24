// Le guide stagionali in PDF.
//
// Cosa difende, e perche' e' una prova e non un commento. Il PDF lo si guarda
// il giorno che si fa e poi mai piu': e' l'unico artefatto del sito che non si
// puo' correggere dopo, perche' una volta scaricato gira per conto suo. Tutti i
// difetti qui sotto sono silenziosi — la run resta verde, la pagina resta
// giusta, e sbagliato e' solo il file che la gente si porta via.
//
// La prova si ADATTA allo stato del repo, e non e' pigrizia: i marker
// GUIDA-PDF li scrive genera_centri.py, che ha bisogno della rete per girare.
// Fra il commit del generatore e la prima run notturna esiste una finestra in
// cui le pagine non li hanno ancora, e pretenderli li' sarebbe una prova rossa
// esattamente quando il sito sta facendo la cosa giusta. E' lo stesso
// adattamento gia' fatto in porte.js per la stagione dei centri e per
// CORSI_IN_INDICE.
'use strict';

const fs = require('fs');
const path = require('path');
const { esito, RADICE } = require('./_aiuto');

const PAGINE = ['centri-estivi.html', 'centri-invernali.html', 'centri-pasquali.html'];

const START = '<!-- GUIDA-PDF:START';
const END = '<!-- GUIDA-PDF:END -->';

function leggi(rel) {
  const p = path.join(RADICE, rel);
  return fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : null;
}

module.exports = async function guide() {
  const r = esito();
  r.titolo('Le guide in PDF — i marker e cosa ci finisce dentro');

  let conMarker = 0;
  for (const file of PAGINE) {
    const s = leggi(file);
    if (s === null) continue;
    const i = s.indexOf(START);
    const j = s.indexOf(END);
    if (i < 0 && j < 0) continue;   // pagina non ancora rigenerata: vedi sopra
    conMarker++;

    // Un marker spaiato e' peggio di nessun marker: estrai() torna null e la
    // guida sparisce in silenzio, senza che niente diventi rosso.
    r.ok(i >= 0 && j > i, `${file}: i marker GUIDA-PDF sono in coppia e in ordine`);
    if (i < 0 || j <= i) continue;
    r.ok(s.indexOf(START, i + 1) < 0, `${file}: un solo blocco GUIDA-PDF`);

    const dentro = s.slice(i, j);

    // Nav e footer nel PDF vorrebbero dire un menu del sito stampato su carta,
    // cioe' due pagine di link morti in cima alla guida.
    r.ok(!/<nav\b/.test(dentro) && !/<footer\b/.test(dentro),
      `${file}: nav e footer restano FUORI dal blocco`);

    // Il difetto piu' facile e piu' imbarazzante: la guida che contiene
    // l'invito a scaricare la guida. Succede appena qualcuno sposta
    // link_guida() di due righe.
    r.ok(!dentro.includes('ce-guidapdf'),
      `${file}: l'invito a scaricare il PDF resta fuori dal PDF`);

    // La prosa e' la ragione per cui uno se la stampa: senza, il PDF e' un
    // elenco, e un elenco lo si guarda meglio sul telefono.
    r.ok(dentro.includes('ce-guide'),
      `${file}: la guida in prosa è dentro il blocco`);
  }
  console.log(`  --   ${conMarker}/${PAGINE.length} pagine centri con i marker`);

  // Il registro e il link. Se il registro nomina un PDF, quel PDF deve
  // esistere: un bottone "Scarica la guida" che porta a un 404 di GitHub e'
  // peggio di nessun bottone, perche' non c'e' una 404 nostra a raccoglierlo.
  const reg = leggi('data/guide.json');
  r.ok(reg !== null, 'data/guide.json esiste (lo scrive genera_pdf.py)');
  if (reg !== null) {
    let voci = {};
    let valido = true;
    try { voci = JSON.parse(reg); } catch (e) { valido = false; }
    r.ok(valido, 'data/guide.json è JSON valido');
    const chiavi = Object.keys(voci);
    console.log(`  --   ${chiavi.length} guide nel registro`);
    for (const k of chiavi) {
      const v = voci[k];
      r.ok(leggi(v.file) !== null, `${k}: il PDF ${v.file} c'è davvero`);
      r.ok(/^\d{4}$/.test(String(v.anno)),
        `${k}: l'anno è nel nome del file (${v.anno})`);
      // L'anno DENTRO il nome del file e' l'unico posto del sito dove ci va: un
      // PDF e' un'istantanea e senza data mente. Se un giorno sparisse, il
      // primo sintomo sarebbe una guida del 2027 scaricata nel 2029.
      r.ok(v.file.includes(String(v.anno)),
        `${k}: il nome del file porta l'anno`);
    }
  }

  // robots.txt. La riga vale piu' di quanto sembri: un PDF indicizzato compete
  // con l'hub che vince la query, e su GitHub Pages non c'e' un X-Robots-Tag
  // con cui rimediare dopo.
  const robots = leggi('robots.txt');
  r.ok(robots !== null && /^Disallow:\s*\/guide\/\s*$/m.test(robots),
    'robots.txt tiene /guide/ fuori dall\'indice');
  if (robots) {
    // Deve stare nel PRIMO gruppo "User-agent: *": Google unisce i gruppi con
    // lo stesso user agent, ma non tutti i parser lo fanno.
    //
    // I commenti si tolgono PRIMA di guardare, ed e' il difetto che questa
    // prova ha trovato appena scritta: robots.txt e' pieno di commenti che
    // spiegano le direttive CITANDOLE, quindi un indexOf sul file grezzo
    // trova "User-agent:" dentro una spiegazione e conclude il falso. Vale
    // per qualunque prova su un file di configurazione commentato.
    const righe = robots.split('\n')
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith('#'));
    const primo = righe.findIndex((l) => /^User-agent:\s*\*$/i.test(l));
    const secondo = righe.findIndex((l, n) => n > primo && /^User-agent:/i.test(l));
    const riga = righe.findIndex((l) => /^Disallow:\s*\/guide\/$/i.test(l));
    r.ok(primo >= 0 && riga > primo && (secondo < 0 || riga < secondo),
      'la riga sta nel primo gruppo User-agent: *');
  }

  return r;
};
