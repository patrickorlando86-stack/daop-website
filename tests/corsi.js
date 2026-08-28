// /corsi.html: i corsi che durano una stagione, una pagina sola.
//
// Quello che si prova qui non e' "la pagina si apre": sono le quattro decisioni
// su cui e' costruita, cioe' quelle che qualcuno smonterebbe per distrazione.
//
//   1. UNA pagina, non una per corso. Non si controlla qui (non c'e' niente da
//      guardare in una pagina che non esiste), ma e' il motivo per cui questa
//      pagina e' fatta cosi': N pagine su template identico col nome scambiato
//      sono scaled content abuse, e i corsi sono la cosa piu' fotocopiabile che
//      abbiamo ("Under 8", "Under 10", "Under 12" della stessa societa').
//   2. Un comando si stampa quando DIVIDE, non quando l'elenco e' lungo.
//   3. L'eta' si CALCOLA da annate + stagione, non si copia dal foglio.
//   4. Nei referenti vanno i NOMI, mai i numeri di telefono.
//   5. Quello che sta in pagina sono CORSI, e ogni realta' ha la sua ancora.
//   6. La riga chiusa porta TRE dati, e sono i tre dei filtri: disciplina,
//      eta', comune. Niente giorni, niente orari, niente nome della societa'.
//   7. Non esistono due livelli di scheda. La presenza e' una sola.
//
// La quinta e' nata da un guasto vero, e le prime quattro non l'avevano preso.
// Il 20/08/2026 alle 02:49 la run notturna ha pubblicato qui le 895 schede del
// catalogo Luoghi al posto dei 5 corsi della PGS Roccavione: la tab del foglio
// era diventata illeggibile, gviz aveva risposto col primo foglio del documento
// e il generatore si era accontentato della colonna 'Nome'. Le quattro prove
// sopra sono passate tutte — l'eta' e i referenti non c'erano, quindi non
// avevano niente da controllare, e i filtri c'erano perche' 895 schede stanno
// sopra la soglia. Passare a vuoto e passare non sono la stessa cosa, e una
// prova che non sa distinguere le due e' una prova che non serve.
//
// La quarta e' l'unica che vale come impegno verso persone vere: sulle
// locandine di partenza c'erano cinque cellulari di volontarie e, a confronto
// con la stagione prima, erano cambiati quasi tutti. Se un giorno qualcuno li
// rimettesse in pagina, questa prova diventa rossa.
'use strict';

const fs = require('fs');
const path = require('path');
const { apri, esito, RADICE } = require('./_aiuto');

module.exports = async function corsi(browser) {
  const r = esito();
  const file = path.join(RADICE, 'corsi.html');
  if (!fs.existsSync(file)) {
    // La pagina nasce solo quando il foglio ha una tab "Attivita". Finche' non
    // c'e', non si inventa un rosso: si dice che si e' saltato.
    console.log('\ncorsi.html — non presente, prove saltate');
    return r;
  }

  r.titolo('corsi.html — telefono 412px');
  const { ctx, page } = await apri(browser, 'corsi.html', 412);

  const schede = await page.locator('.event-card').count();
  r.ok(schede > 0, `${schede} corsi in pagina`);

  // ── 2. un comando si stampa quando DIVIDE, non quando l'elenco e' lungo ─
  // La soglia di conteggio (sotto 12 corsi niente barra) e' caduta il
  // 20/08/2026, per decisione di Patrick. Il criterio che resta guarda i dati
  // invece di contarli, ed e' migliore: dodici corsi tutti 6-8 anni non hanno
  // bisogno di una tendina eta', cinque corsi da 6 a 14 anni si'.
  //
  // La prova e' a DUE facce apposta: se nessun campo dividerebbe la barra NON
  // deve esserci, se almeno uno divide deve esserci. Una prova che controlla
  // solo il caso in cui la barra c'e' passerebbe a vuoto su una pagina che non
  // la stampa piu' per sbaglio.
  const toolbar = await page.locator('#co-toolbar').count();
  const distinti = await page.$$eval('.event-card', (cs) => {
    const quanti = (f) => new Set(cs.map(f).filter(Boolean)).size;
    // Le stesse fasce di FASCE_ETA, confrontate per sovrapposizione come nel
    // generatore: un corso 6-11 tocca sia "6-8" sia "9-11".
    const FASCE = [[0, 3], [3, 5], [6, 8], [9, 11], [12, 14], [15, 99]];
    const fasce = new Set();
    cs.forEach((c) => {
      const lo = Number(c.dataset.etamin);
      const hi = Number(c.dataset.etamax);
      if (!Number.isFinite(lo) || !Number.isFinite(hi)) return;
      FASCE.forEach(([a, b]) => { if (lo <= b && hi >= a) fasce.add(a + "-" + b); });
    });
    return {
      cat: quanti((c) => c.dataset.cat),
      citta: quanti((c) => c.dataset.city),
      fasce: fasce.size,
    };
  });
  const divide = distinti.cat > 1 || distinti.citta > 1 || distinti.fasce > 1;
  r.ok(toolbar === (divide ? 1 : 0),
    `attivita ${distinti.cat}, comuni ${distinti.citta}, fasce eta ${distinti.fasce}`
    + ` -> ${divide ? "almeno un comando divide" : "nessun comando dividerebbe"}`
    + `, barra ${toolbar ? "stampata" : "non stampata"}`);

  if (toolbar) {
    // Una tendina con una voce sola e' un comando che non fa niente.
    const inutili = await page.$$eval('#co-toolbar select', (sels) =>
      sels.filter((s) => s.options.length <= 2).map((s) => s.getAttribute('data-campo')));
    r.ok(inutili.length === 0, inutili.length
      ? `tendine con una scelta sola: ${inutili.join(', ')}`
      : 'ogni tendina ha almeno due scelte vere');
    // Nessuna voce di tendina puo' dare zero risultati. E' la stessa regola
    // della tendina con una voce sola, un gradino piu' in la': "0-3 anni" su
    // una pagina che parte dai 6 e' un comando che non fa niente, e chi lo
    // sceglie si trova la pagina vuota e pensa che il filtro sia rotto.
    const aVuoto = [];
    for (const campo of await page.$$eval('#co-toolbar select',
      (ss) => ss.map((s2) => s2.getAttribute('data-campo')))) {
      const sel = page.locator(`#co-toolbar [data-campo="${campo}"]`);
      const valori = await sel.evaluate((s2) => [...s2.options].map((o) => o.value).slice(1));
      for (const v of valori) {
        await sel.selectOption(v);
        await page.waitForTimeout(120);
        const rimaste = await page.$$eval('.event-card',
          (cs) => cs.filter((c) => c.offsetParent !== null).length);
        if (rimaste === 0) aVuoto.push(`${campo}=${v}`);
      }
      await sel.selectOption('all');
      await page.waitForTimeout(120);
    }
    r.ok(aVuoto.length === 0, aVuoto.length
      ? `voci di tendina che svuotano la pagina: ${aVuoto.join(', ')}`
      : 'nessuna voce di tendina porta a zero risultati');

    // Con zero corsi visibili non deve restare in piedi la sezione delle
    // realta' in fondo: sono schede di societa' di cui in pagina non e'
    // rimasto nessun corso, cioe' esattamente il vuoto sospeso di prima
    // spostato piu' giu'. Il titolo della sezione sta FUORI dalle schede, ed e'
    // il pezzo che resta in aria se ci si dimentica di nasconderlo.
    await page.locator('#co-q').fill('zzzznessuno');
    await page.waitForTimeout(250);
    const rimaste = await page.$$eval('.co-realta',
      (hs) => hs.filter((h) => h.offsetParent !== null).length);
    r.ok(rimaste === 0, 'con zero risultati non resta nessuna scheda realtà');
    const titolo = await page.locator('#realta').evaluate(
      (el) => el.offsetParent !== null).catch(() => false);
    r.ok(titolo === false, 'e nemmeno il titolo della sezione, sospeso sul vuoto');
    await page.locator('#co-q').fill('');
    await page.waitForTimeout(250);

    // Un filtro che lascia in piedi i corsi di una sola societa' deve lasciare
    // in piedi una sola scheda: se restassero tutte, la sezione in fondo
    // smentirebbe il filtro appena usato.
    const cat = page.locator('#co-toolbar [data-campo="cat"]');
    if (await cat.count()) {
      const primo = await cat.evaluate((s2) => s2.options[1].value);
      await cat.selectOption(primo);
      await page.waitForTimeout(200);
      const orgVivi = await page.$$eval('.event-card',
        (cs) => [...new Set(cs.filter((c) => c.offsetParent !== null)
          .map((c) => c.dataset.org))]);
      const schedeVive = await page.$$eval('.co-realta',
        (hs) => hs.filter((h) => h.offsetParent !== null).map((h) => h.dataset.org));
      r.ok(schedeVive.length === orgVivi.length
        && schedeVive.every((o) => orgVivi.includes(o)),
        `filtrando "${primo}" restano ${orgVivi.length} realtà nei corsi `
        + `e ${schedeVive.length} schede in fondo`);
      await cat.selectOption('all');
      await page.waitForTimeout(200);
    }
  }


  // ── il dettaglio si apre e dice qualcosa ──────────────────────────────
  await page.locator('.event-card .ev-row').first().click();
  await page.waitForTimeout(200);
  const det = page.locator('.event-card .ev-det').first();
  r.ok(await det.evaluate((d) => !d.hidden), 'la riga si apre al tocco');
  r.ok((await det.innerText()).trim().length > 20, 'aperta, la riga dice qualcosa');

  // ── 3. l'eta' in riga: O calcolata dalle annate, O scritta sulla locandina ─
  // Fino al 26/08/2026 qui si provava una regola sola: la fascia in riga DEVE
  // essere quella calcolata da annate + stagione. Nasceva giusta - un'eta'
  // dedotta dalle annate slitta di un anno a ogni stagione, e una colonna
  // scritta a mano a settembre pubblica la fascia dell'anno prima.
  //
  // Ma le annate le stampano le societa' sportive, non le scuole di musica: sui
  // volantini di Crome c'era "per bambini 3-5 anni", "a partire dai 4 anni".
  // Buttarle voleva dire sei corsi su sei fuori dalla tendina eta', ed e' stato
  // il primo rilievo di Giovanni sulla pagina ("manca l'eta': fondamentale,
  // altrimenti non funzionano i filtri"). Un'eta' STAMPATA non invecchia:
  // descrive il corso, non un gruppo di nati.
  //
  // Quindi le regole sono due, e la scheda dice quale vale (data-etada). La
  // prova le tiene separate a posta: se un domani il ramo "annate" tornasse a
  // copiare una colonna scritta a mano, questa resta rossa come prima.
  const incoerenti = await page.$$eval('.event-card[data-etamin]', (cards) =>
    cards.filter((c) => {
      const lo = c.dataset.etamin, hi = c.dataset.etamax;
      const riga = c.querySelector('.ev-line').textContent;
      if (c.dataset.etada === 'testo') {
        // Il ramo "scritta": in riga ci deve stare l'eta' come l'ha scritta la
        // locandina, e almeno il numero di partenza deve tornare con la fascia
        // usata dal filtro - se no il filtro e la riga direbbero due cose.
        //
        // "0-12 mesi" (il massaggio infantile) e' il caso in cui le due
        // unita' non coincidono: la riga tiene quella della locandina, il
        // filtro conta anni. Quello che deve tornare e' che la conversione
        // ci sia stata (_eta_numeri in genera_corsi.py) - un corso per
        // lattanti non puo' occupare una fascia larga di anni. Fino al
        // 28/08/2026 questa prova pretendeva la parola "anni" in riga, ed
        // era rossa su un corso scritto nel modo giusto.
        if (/mes/i.test(riga)) return !(Number(hi) <= 2);
        return !new RegExp(`\\b${lo}\\b`).test(riga) || !/ann/i.test(riga);
      }
      const atteso = lo === hi ? `${lo} anni` : `${lo}-${hi} anni`;
      return !riga.includes(atteso);
    }).map((c) => `${c.querySelector('.ev-name').textContent.trim()}`
      + ` [${c.dataset.etada}]`));
  const daAnnate = await page.$$eval('.event-card[data-etada="annate"]', (c) => c.length);
  const daTesto = await page.$$eval('.event-card[data-etada="testo"]', (c) => c.length);
  r.ok(incoerenti.length === 0, incoerenti.length
    ? `eta' in riga incoerente: ${incoerenti.join(', ')}`
    : `l'eta' in riga torna su tutte: ${daAnnate} calcolate dalle annate, `
      + `${daTesto} scritte sulla locandina`);

  // ── 4. nei referenti i nomi, mai i numeri ─────────────────────────────
  const conNumero = await page.$$eval('.co-dati', (dls) => {
    const fuori = [];
    dls.forEach((dl) => {
      const dts = [...dl.querySelectorAll('dt')];
      dts.forEach((dt) => {
        if (!/referent/i.test(dt.textContent)) return;
        const dd = dt.nextElementSibling;
        // sei cifre di fila = un numero di telefono, comunque sia spaziato
        if (dd && /(\d[\s.\-/]*){6,}/.test(dd.textContent)) fuori.push(dd.textContent.trim());
      });
    });
    return fuori;
  });
  r.ok(conNumero.length === 0, conNumero.length
    ? `numeri di telefono dentro i Referenti: ${conNumero.join(' | ')}`
    : 'i referenti sono nomi, senza numeri personali');

  // ── il titolo non promette province che non ci sono ───────────────────
  const h1 = (await page.locator('h1').first().innerText()).toLowerCase();
  const provInPagina = await page.$$eval('.event-card[data-prov]',
    (cs) => [...new Set(cs.map((c) => c.dataset.prov).filter(Boolean))]);
  const NOMI = { al: 'alessandria', at: 'asti', cn: 'cuneo', to: 'torino' };
  const promesse = Object.entries(NOMI)
    .filter(([sigla, nome]) => h1.includes(nome) && !provInPagina.includes(sigla))
    .map(([, nome]) => nome);
  r.ok(promesse.length === 0, promesse.length
    ? `il titolo nomina province senza corsi: ${promesse.join(', ')}`
    : 'il titolo nomina solo le province che hanno davvero dei corsi');

  // ── le schede realta' non sono <section> ──────────────────────────────
  // section{padding:100px 24px} arriva dal CSS di sistema: una scheda nascosta
  // dai filtri lascerebbe 200px di niente in fondo alla pagina.
  r.ok(await page.$$eval('.co-realta', (hs) => hs.every((h) => h.tagName !== 'SECTION')),
    'le schede realta\' sono <div>, non <section> (la trappola del padding)');
  const wrap = await page.locator('#realta').evaluate((el) => el.tagName)
    .catch(() => 'ASSENTE');
  r.ok(wrap !== 'SECTION', `il contenitore delle realtà è <${wrap.toLowerCase()}>`);

  // ── 5a. ogni realta' ha la sua ancora, e non sono tutte nel raccoglitore ─
  // E' il link che Giovanni manda alle societa' ("guarda, questa e' la tua
  // paginetta"): #r-pgs-roccavione. Nasce dalla colonna Organizzatore, e quando
  // il generatore legge il foglio sbagliato quella colonna non c'e' — quindi
  // TUTTO finisce nel gruppo di scarto "Altre realta'" e l'ancora non esiste
  // piu'. Il browser, davanti a un frammento che non trova, non sbaglia in modo
  // visibile: resta in cima alla pagina. Ed e' esattamente il sintomo con cui il
  // guasto e' stato segnalato.
  const gruppi = await page.$$eval('.co-realta', (hs) => hs.map((h) => ({
    id: h.id, testo: h.textContent.trim().slice(0, 60) })));
  r.ok(gruppi.length > 0, `${gruppi.length} gruppi realta' in pagina`);

  const senzaAncora = gruppi.filter((g) => !/^r-.+/.test(g.id)).map((g) => g.testo);
  r.ok(senzaAncora.length === 0, senzaAncora.length
    ? `gruppi senza ancora linkabile: ${senzaAncora.join(' | ')}`
    : "ogni gruppo realta' ha la sua ancora r-…");

  const doppie = gruppi.map((g) => g.id).filter((id, i, a) => a.indexOf(id) !== i);
  r.ok(doppie.length === 0, doppie.length
    ? `ancore doppie, il link va sul gruppo sbagliato: ${doppie.join(', ')}`
    : "le ancore delle realta' sono tutte diverse");

  // Un gruppo "Altre realta'" ci sta: una riga puo' non avere l'organizzatore.
  // Che ci sia SOLO quello vuol dire che la colonna non e' stata letta.
  const vere = gruppi.filter((g) => g.id !== 'r-altre-realta');
  r.ok(vere.length > 0, vere.length
    ? `${vere.length} realta’ con un nome proprio e un link da mandare in giro`
    : "tutti i corsi sono in \"Altre realta'\": la colonna Organizzatore non e' "
      + "stata letta (foglio sbagliato?), e nessuna societa’ ha un link suo");

  // ── 6. la riga chiusa porta TRE dati, e non uno di piu' ──────────────
  // Richiesta di Giovanni del 21/08/2026: disciplina, eta', comune. Quello che
  // NON ci sta e' altrettanto deciso — i giorni e gli orari (troppo lunghi, e
  // servono a chi ha gia' scelto) e il nome della societa' (in questa pagina si
  // sceglie un corso, non una societa'). Sono le due cose che qualcuno
  // rimetterebbe in riga pensando di aggiungere informazione.
  const inRiga = await page.$$eval('.event-card', (cs) => cs.map((c) => ({
    nome: c.querySelector('.ev-name').textContent.trim(),
    linea: c.querySelector('.ev-line').textContent.trim(),
    cat: (c.querySelector('.co-cat') || {}).textContent || '',
    org: c.dataset.org || '',
  })));
  // Un giorno della settimana o un orario in riga: e' il segno che i giorni
  // sono risaliti dal dettaglio.
  const GIORNI = /luned|marted|mercoled|gioved|venerd|sabato|domenica|\d{1,2}[.:]\d{2}/i;
  const conGiorni = inRiga.filter((c) => GIORNI.test(c.linea)).map((c) => c.nome);
  r.ok(conGiorni.length === 0, conGiorni.length
    ? `giorni o orari tornati in riga: ${conGiorni.join(', ')}`
    : "in riga non ci sono giorni ne' orari");
  // La disciplina invece ci deve stare, e su ogni riga: e' il primo dato utile
  // in un elenco che mescola pallavolo e teatro.
  const senzaCat = inRiga.filter((c) => !c.cat.trim()).map((c) => c.nome);
  r.ok(senzaCat.length === 0, senzaCat.length
    ? `righe senza disciplina scritta: ${senzaCat.join(', ')}`
    : `la disciplina e' scritta su tutte e ${inRiga.length} le righe`);

  // ── 7. non esistono due livelli di scheda ────────────────────────────
  // Dal 21/08/2026 la presenza nella guida e' una sola e uguale per tutti: una
  // pillola "scheda completa" distinguerebbe da niente, e un invito che dice
  // "gratuita" e' una promessa che poi va ritirata. Sono le due cose che
  // tornerebbero se qualcuno ripescasse la versione di prima.
  const pillole = await page.$$eval('.ev-pill',
    (ps) => [...new Set(ps.map((p2) => p2.textContent.trim()))]);
  r.ok(!pillole.some((t) => /completa|premium|★/i.test(t)),
    `pillole in pagina: ${pillole.join(' | ') || 'nessuna'}`);
  const testo = fs.readFileSync(file, 'utf8');
  r.ok(!/scheda è gratuita|scheda e' gratuita|gratuit[ao] e la compiliamo/i.test(testo),
    "l'invito alle societa' non promette una scheda gratuita");
  // E l'invito deve comunque dire a chi si scrive: senza un indirizzo e' un
  // cartello, non un invito.
  const mail = await page.$$eval('.co-nota a[href^="mailto:"]',
    (as) => as.map((a) => a.getAttribute('href').replace('mailto:', '')));
  r.ok(mail.length > 0, mail.length
    ? `l'invito porta un indirizzo: ${mail.join(', ')}`
    : "l'invito alle societa' non dice a chi scrivere");

  // ── l'organizzatore sta nel dettaglio, e il suo link arriva a destinazione ─
  // E' l'altra meta' della decisione: tolto dalla riga, deve esserci sotto — e
  // deve portare a un'ancora che esiste davvero. Un link a un frammento
  // inesistente non sbaglia in modo visibile: il browser resta dov'e', ed e'
  // il sintomo con cui si segnalano questi guasti.
  const legami = await page.$$eval('.co-dati dt', (dts) => dts
    .filter((dt) => /organizzator/i.test(dt.textContent))
    .map((dt) => {
      const a = dt.nextElementSibling.querySelector('a');
      return a ? a.getAttribute('href') : null;
    }));
  r.ok(legami.length > 0 && legami.every(Boolean),
    `${legami.length} corsi rimandano al loro organizzatore`);
  // Due destinazioni possibili e nessuna delle due puo' essere inventata: se la
  // realta' ha una pagina dedicata si va li', se no all'ancora del riassunto in
  // fondo. Sono due controlli diversi — un'ancora si cerca nel DOM, un file si
  // cerca su disco — e confonderli e' facile: page.locator('/corsi/x.html')
  // non e' un selettore, e' un errore.
  const persi = [];
  for (const h of [...new Set(legami.filter(Boolean))]) {
    if (h.startsWith('#')) {
      if (await page.locator(h).count() === 0) persi.push(h + ' (ancora)');
    } else if (!fs.existsSync(path.join(RADICE, h.replace(/^\//, '')))) {
      persi.push(h + ' (file)');
    }
  }
  r.ok(persi.length === 0, persi.length
    ? `link organizzatore che non arrivano da nessuna parte: ${persi.join(', ')}`
    : 'ogni link organizzatore arriva a destinazione');

  // ── niente "Iscrizioni aperte/chiuse" ────────────────────────────────
  // Tolto il 21/08/2026: e' un dato che scade in silenzio e che nessuno viene
  // ad aggiornare. Se torna, torna sbagliato a gennaio.
  const iscr = await page.$$eval('.co-dati dt',
    (dts) => dts.filter((dt) => /iscrizion/i.test(dt.textContent)).length);
  r.ok(iscr === 0, iscr
    ? `${iscr} schede dichiarano lo stato delle iscrizioni`
    : 'nessuna scheda dichiara "iscrizioni aperte/chiuse"');

  // ── 5b. questa pagina non e' il catalogo dei luoghi ─────────────────
  // Il controllo vero sta nel generatore (CHIAVI_CORSO in genera_corsi.py), che
  // rifiuta un foglio senza Organizzatore/Annate/Stagione. Questo lo ricontrolla
  // dall'altro capo, sul file pubblicato: se un domani il ripiego cambia, il
  // rosso arriva qui e non da un lettore che ci scrive.
  //
  // La soglia e' larga apposta: una societa' sportiva sta legittimamente in
  // tutti e due i cataloghi — la PGS Roccavione e' un corso E un luogo. Quello
  // che non e' legittimo e' che si somiglino per meta'.
  const fileLuoghi = path.join(RADICE, 'luoghi.html');
  if (fs.existsSync(fileLuoghi)) {
    const nomi = (testo, cls) => new Set(
      [...testo.matchAll(new RegExp(`class="${cls}"[^>]*>([^<]{2,90})`, 'g'))]
        .map((m) => m[1].trim().toLowerCase()).filter(Boolean));
    const qui = nomi(fs.readFileSync(file, 'utf8'), 'ev-name');
    const la = nomi(fs.readFileSync(fileLuoghi, 'utf8'), 'lg-nome');
    const comuni = [...qui].filter((n) => la.has(n));
    const quota = qui.size ? comuni.length / qui.size : 0;
    r.ok(quota < 0.5,
      `${comuni.length} nomi su ${qui.size} stanno anche in luoghi.html `
      + `(${Math.round(quota * 100)}%)`
      + (quota < 0.5 ? '' : ' — questa pagina sta pubblicando i LUOGHI, non i corsi'));
  }

  // ── 6. un open day non manda mai su una pagina che non esiste ─────────
  // Il legame lo scrive una persona in una cella (colonna OpenDay del corso, e
  // dentro va il NOME dell'evento). Una persona scrive male, o rinomina
  // l'evento in Eventi e si dimentica del corso: allora openday() deve tacere,
  // non stampare un link che scarica su un 404.
  //
  // Oggi nel foglio non c'e' nessun open day, quindi questa prova conta zero
  // link — e il conteggio si stampa APPOSTA. E' la lezione del 20/08: una prova
  // che passa a vuoto e una che passa si somigliano troppo, e per un mese
  // nessuno se ne accorge.
  const openday = await page.$$eval('.co-openday a', (as) => as.map((a) => ({
    href: a.getAttribute('href'), testo: a.closest('.co-openday').textContent.trim() })));
  const rotti = openday.filter((o) => {
    if (!/^\/eventi\/[^/]+\.html$/.test(o.href || '')) return true;
    return !fs.existsSync(path.join(RADICE, o.href.replace(/^\//, '')));
  }).map((o) => o.href);
  r.ok(rotti.length === 0, rotti.length
    ? `open day che puntano a pagine inesistenti: ${rotti.join(', ')}`
    : `${openday.length} link a open day, tutti verso schede che esistono`);

  // ── 7. ogni riga sa di chi e', e il tracciamento lo legge ────────────
  // Chiesto da Giovanni il 21/08/2026: restituire a ogni realta' il proprio
  // percorso (scheda aperta -> sito -> telefono -> email -> social) senza
  // ricostruire l'organizzatore dall'URL di destinazione. Il legame e' un
  // attributo nel DOM, e se sparisce non si rompe NIENTE di visibile: la
  // pagina resta identica e i report si svuotano in silenzio. Per questo la
  // prova sta qui e non nella pagina.
  const senzaOrg = await page.$$eval('.event-card, .co-realta', (els) => els
    .filter((e) => !(e.dataset.org || '').trim() || !(e.dataset.orgNome || '').trim())
    .map((e) => e.id || e.textContent.trim().slice(0, 40)));
  r.ok(senzaOrg.length === 0, senzaOrg.length
    ? `righe senza attribuzione (data-org / data-org-nome): ${senzaOrg.join(' | ')}`
    : "ogni corso e ogni realta' portano id e nome dell'organizzatore");

  // Il telefono e' una TAPPA DEL PERCORSO, e un numero stampato come testo non
  // produce un clic: in GA4 quella colonna resterebbe vuota per sempre. Vale
  // anche per chi legge — su un telefono si chiama toccando.
  const telSpenti = await page.$$eval('.co-dati', (dls) => {
    const fuori = [];
    dls.forEach((dl) => {
      [...dl.querySelectorAll('dt')].forEach((dt) => {
        if (!/contatt/i.test(dt.textContent)) return;
        const dd = dt.nextElementSibling;
        if (!dd) return;
        // sei cifre di fila = un numero, comunque sia spaziato
        if (!/(\d[\s.\-/]*){6,}/.test(dd.textContent)) return;
        if (!dd.querySelector('a[href^="tel:"]')) fuori.push(dd.textContent.trim());
      });
    });
    return fuori;
  });
  r.ok(telSpenti.length === 0, telSpenti.length
    ? `numeri non cliccabili nei Contatti: ${telSpenti.join(' | ')}`
    : 'i numeri nei Contatti sono link tel:, quindi si chiamano e si contano');

  await ctx.close();

  // ── 9. le pagine dedicate delle realta' ──────────────────────────────
  // Chieste da Giovanni il 21/08/2026 ("una pagina organizzatori, non solo la
  // scheda nella pagina generale"). Sono la cosa piu' vicina allo scaled
  // content che questo sito abbia: N pagine su un template solo, col nome
  // scambiato. Quello che le rende legittime non e' il numero, e' il
  // MATERIALE — descrizione vera, contatti, corsi, eventi — quindi la prova
  // guarda proprio quello, non che il file esista.
  //
  // Il caso "nessuna pagina" e' legittimo e va detto, non saltato in silenzio:
  // finche' la tab Realta non ha descrizioni, la pagina non deve nascere.
  const dedicate = fs.existsSync(path.join(RADICE, 'corsi'))
    ? fs.readdirSync(path.join(RADICE, 'corsi')).filter((f) => f.endsWith('.html'))
    : [];
  r.titolo(`pagine realtà — ${dedicate.length} in /corsi/`);
  if (!dedicate.length) {
    console.log('  --   nessuna realtà ha materiale a sufficienza: '
      + 'nessuna pagina dedicata, ed è il comportamento voluto');
  }
  // Ogni pagina dedicata dev'essere raggiungibile da corsi.html: una pagina che
  // non riceve link dal corpo di nessun'altra e' orfana, ed e' il guasto gia'
  // costato tutto il traffico a luoghi.html.
  const hub = fs.readFileSync(file, 'utf8');
  const fileSitemap = path.join(RADICE, 'sitemap.xml');
  const sitemap = fs.existsSync(fileSitemap)
    ? fs.readFileSync(fileSitemap, 'utf8') : '';
  for (const f of dedicate) {
    const q = await apri(browser, `corsi/${f}`, 412);
    const h1 = (await q.page.locator('h1').first().innerText()).trim();
    const org = await q.page.locator('[data-org-nome]').first()
      .getAttribute('data-org-nome').catch(() => null);
    r.ok(!!h1 && h1 === (org || h1), `${f}: l'H1 è la realtà (${h1})`);

    const corsiQui = await q.page.locator('.event-card').count();
    r.ok(corsiQui > 0, `${f}: ${corsiQui} corsi in pagina`);

    // Il materiale che giustifica la pagina. Senza descrizione questa pagina
    // dice meno della scheda che la realta' ha gia' in corsi.html, cioe' e' un
    // doppione piu' debole del proprio riassunto.
    // textContent e non innerText, e su TUTTI i paragrafi. Due ragioni, ed
    // entrambe sono cambiamenti del 26/08/2026: la descrizione esce in
    // paragrafi (una persona che scrive di se' va a capo, e prima finivano
    // schiacciati in un <p> solo), e sta dentro un <details> che nasce chiuso
    // (Giovanni: "posso anche non volerla leggere"). innerText su un elemento
    // chiuso torna vuoto, e su un locator che pesca sei paragrafi non torna
    // affatto. Quello che questa prova deve garantire non e' "si vede adesso":
    // e' "il materiale che giustifica la pagina c'e'".
    const descr = await q.page.$$eval('.cr-descr',
      (ps) => ps.map((p) => p.textContent).join(' ')).catch(() => '');
    r.ok(descr.trim().length >= 120,
      `${f}: descrizione di ${descr.trim().length} caratteri`);

    // Sulla propria pagina la riga "Organizzatore" non si stampa: sarebbe un
    // link all'intestazione che si sta leggendo.
    const seStesso = await q.page.$$eval('.co-dati dt',
      (dts) => dts.filter((dt) => /organizzator/i.test(dt.textContent)).length);
    r.ok(seStesso === 0, `${f}: nessuna riga "Organizzatore" verso se stessa`);

    // robots e sitemap d'accordo, che e' l'invariante che aggiorna_sitemap
    // dichiara di se': una URL in sitemap con robots noindex sono due ordini
    // che si contraddicono.
    //
    // NON si confronta piu' con l'hub, e il perche' vale la pena saperlo. Dal
    // 26/08/2026 la pagina di una realta' entra in indice quando la SUA riga
    // dice "confermata" (confermata() in genera_corsi.py), mentre
    // CORSI_IN_INDICE resta padrone del solo hub: sono due decisioni
    // deliberatamente indipendenti - una sulla sezione, una sulla societa'.
    // "Uguale all'hub" diventava rossa alla prima realta' che confermava,
    // cioe' proprio quando il sito faceva la cosa giusta.
    const rob = await q.page.locator('meta[name="robots"]')
      .getAttribute('content').catch(() => '');
    r.ok(/^(no)?index, follow$/.test(rob), `${f}: robots "${rob}"`);
    const inSitemap = sitemap.includes(`/corsi/${f}<`);
    r.ok(!(inSitemap && /noindex/.test(rob)),
      `${f}: ${inSitemap ? 'in sitemap' : 'fuori sitemap'} e robots "${rob}"`);

    const can = await q.page.locator('link[rel="canonical"]')
      .getAttribute('href').catch(() => '');
    r.ok(can.endsWith(`/corsi/${f}`), `${f}: canonical su se stessa (${can})`);

    // Le locandine degli eventi: se ce ne sono, i link devono esistere.
    const ev = await q.page.$$eval('.cr-ev', (as) => as.map((a) => a.getAttribute('href')));
    const evRotti = ev.filter((h) => !fs.existsSync(path.join(RADICE, h.replace(/^\//, ''))));
    r.ok(evRotti.length === 0, evRotti.length
      ? `${f}: eventi verso pagine inesistenti: ${evRotti.join(', ')}`
      : `${f}: ${ev.length} eventi, tutti verso schede che esistono`);

    r.ok(hub.includes(`/corsi/${f}`),
      `${f}: corsi.html la linka (non è orfana)`);
    await q.ctx.close();
  }

  // ── 8. l'attribuzione arriva davvero in GA4 ──────────────────────────
  // Si riapre la pagina con uno stub al posto di gtag: quello che si prova non
  // e' che il DOM abbia gli attributi (l'ha appena detto la 7), e' che
  // daop-track.js li sappia risalire. Il preventDefault sta su window e non su
  // document APPOSTA: in fase di capture window viene prima, quindi il clic
  // arriva comunque all'ascoltatore del tracciamento ma la pagina non naviga.
  const spia = () => {
    window.addEventListener('click', (e) => e.preventDefault(), true);
  };
  const b = await apri(browser, 'corsi.html', 412, spia);
  // Il consenso si accende DOPO il caricamento, non nello script iniziale:
  // cookie-consent.js parte mettendo `daopConsensoAnalytics = false`, quindi un
  // flag acceso prima verrebbe spento da lui e la prova misurerebbe il banner.
  await b.page.evaluate(() => {
    window.__ga = [];
    window.daopConsensoAnalytics = true;
    window.gtag = function () { window.__ga.push([].slice.call(arguments)); };
  });

  // L'APERTURA DELLA SCHEDA: e' il denominatore di tutto il resto. Senza, a una
  // realta' si puo' dire "3 clic al tuo sito" ma non su quante volte.
  await b.page.locator('.event-card[data-org] .ev-row').first().click();
  const aperture = await b.page.evaluate(
    () => window.__ga.filter((e) => e[1] === 'apri_corso').map((e) => e[2]));
  r.ok(aperture.length === 1, `apri_corso: ${aperture.length} evento/i su un'apertura`);
  const a0 = aperture[0] || {};
  r.ok(!!(a0.organizer_id && a0.organizer_name && a0.course_id && a0.course_name),
    aperture.length
      ? `apri_corso porta ${JSON.stringify(a0.organizer_id)} / ${JSON.stringify(a0.course_name)}`
      : "apri_corso non e' arrivato: l'apertura di una scheda non si misura");
  // Richiudere non e' un secondo interessamento.
  await b.page.locator('.event-card[data-org] .ev-row').first().click();
  r.ok((await b.page.evaluate(
    () => window.__ga.filter((e) => e[1] === 'apri_corso').length)) === 1,
    'la chiusura di una scheda non conta come una seconda apertura');

  // I clic in uscita DENTRO una scatola con un padrone: sito, telefono, email,
  // social. Il conteggio si stampa apposta — oggi il foglio ha poche colonne
  // compilate, e una prova che passa a vuoto va distinta da una che passa.
  // I dettagli si aprono prima: i recapiti di un corso vivono dentro
  // `.ev-det[hidden]`, e un link nascosto non si puo' cliccare. E' anche
  // l'ordine vero — nessuno telefona senza aver aperto la scheda.
  for (const riga of await b.page.locator('.event-card[data-org] .ev-row').all()) {
    await riga.click();
  }
  // SI ITERA SUGLI ELEMENTI, NON SUGLI HREF. Prima si raccoglievano gli href e
  // per ognuno si cliccava `[href="..."]`.first(): con due corsi che portano lo
  // stesso numero — cioe' con una societa' che ha sei corsi e un telefono solo,
  // il caso normale — si cliccava tre volte la STESSA ancora e le ripetizioni
  // risultavano non tracciate. Il sito non c'entrava niente: era la prova a
  // contare male, e lo si e' visto solo il 26/08/2026, quando in pagina e'
  // entrata la prima societa' con piu' di un corso allo stesso recapito.
  const esterni = await b.page.locator(
    '[data-org] a[href^="tel:"], [data-org] a[href^="mailto:"], '
    + '[data-org] a[href^="http:"], [data-org] a[href^="https:"]').all();
  let orfani = 0;
  for (const ancora of esterni) {
    const href = await ancora.getAttribute('href');
    await b.page.evaluate(() => { window.__ga = []; });
    await ancora.click();
    // Non `__ga[0]`: aprendo i dettagli la pagina cambia altezza e uno
    // `scroll_depth` puo' infilarsi davanti al clic. Si cerca la destinazione.
    const p = await b.page.evaluate((h) => {
      const e = window.__ga.find((x) => x[2] && x[2].destination_url === h);
      return e ? e[2] : null;
    }, href);
    if (!p || !p.organizer_id) orfani += 1;
  }
  r.ok(orfani === 0, orfani
    ? `${orfani} clic su ${esterni.length} non sono attribuiti a nessuna realta'`
    : `${esterni.length} clic in uscita dentro una scheda, tutti attribuiti`);

  // E IL CONTRARIO, che e' la meta' che si dimentica: un link che non sta
  // dentro la scheda di nessuno — l'invito alle societa' in fondo, il footer —
  // non deve prendersi l'attribuzione dell'ultima realta' della pagina.
  await b.page.evaluate(() => { window.__ga = []; });
  const fuoriBox = b.page.locator('.co-nota a[href^="mailto:"]').first();
  if (await fuoriBox.count()) {
    const suo = await fuoriBox.getAttribute('href');
    await fuoriBox.click();
    const p = await b.page.evaluate((h) => {
      const e = window.__ga.find((x) => x[2] && x[2].destination_url === h);
      return e ? e[2] : null;
    }, suo);
    r.ok(!!p && !p.organizer_id,
      !p
        ? "il clic fuori dalle schede non ha prodotto nessun evento (stub muto?)"
        : p.organizer_id
          ? `un link fuori dalle schede e' attribuito a ${p.organizer_id}`
          : "un link fuori dalle schede non e' attribuito a nessuna realta'");
  }

  await b.ctx.close();
  return r;
};
