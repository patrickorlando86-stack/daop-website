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
//   2. Sotto MIN_FILTRI la barra dei filtri NON si stampa.
//   3. L'eta' si CALCOLA da annate + stagione, non si copia dal foglio.
//   4. Nei referenti vanno i NOMI, mai i numeri di telefono.
//   5. Quello che sta in pagina sono CORSI, e ogni realta' ha la sua ancora.
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

  // ── 2. i filtri solo quando si guadagnano il posto ────────────────────
  const MIN = 12;
  const toolbar = await page.locator('#co-toolbar').count();
  if (schede < MIN) {
    r.ok(toolbar === 0,
      `sotto ${MIN} corsi la barra dei filtri non si stampa (${schede} corsi)`);
  } else {
    r.ok(toolbar === 1, `sopra ${MIN} corsi la barra dei filtri c'e'`);
    // Una tendina con una voce sola e' un comando che non fa niente.
    const inutili = await page.$$eval('#co-toolbar select', (sels) =>
      sels.filter((s) => s.options.length <= 2).map((s) => s.getAttribute('data-campo')));
    r.ok(inutili.length === 0, inutili.length
      ? `tendine con una scelta sola: ${inutili.join(', ')}`
      : 'ogni tendina ha almeno due scelte vere');
    // Un gruppo svuotato dai filtri si porta via la sua intestazione: il titolo
    // sta PRIMA del gruppo e fuori da esso, ed e' il caso che resta in aria.
    await page.locator('#co-q').fill('zzzznessuno');
    await page.waitForTimeout(250);
    const titoliRimasti = await page.$$eval('.co-realta',
      (hs) => hs.filter((h) => h.offsetParent !== null).length);
    r.ok(titoliRimasti === 0, 'con zero risultati non resta in aria nessuna intestazione');
    await page.locator('#co-q').fill('');
    await page.waitForTimeout(250);
  }

  // ── il dettaglio si apre e dice qualcosa ──────────────────────────────
  await page.locator('.event-card .ev-row').first().click();
  await page.waitForTimeout(200);
  const det = page.locator('.event-card .ev-det').first();
  r.ok(await det.evaluate((d) => !d.hidden), 'la riga si apre al tocco');
  r.ok((await det.innerText()).trim().length > 20, 'aperta, la riga dice qualcosa');

  // ── 3. l'eta' mostrata e' quella calcolata dalle annate ───────────────
  // Se un giorno l'eta' tornasse a essere copiata da una colonna scritta a
  // mano, a settembre la pagina pubblicherebbe la fascia dell'anno prima.
  const incoerenti = await page.$$eval('.event-card[data-etamin]', (cards) =>
    cards.filter((c) => {
      const lo = c.dataset.etamin, hi = c.dataset.etamax;
      const atteso = lo === hi ? `${lo} anni` : `${lo}-${hi} anni`;
      return !c.querySelector('.ev-line').textContent.includes(atteso);
    }).map((c) => c.querySelector('.ev-name').textContent.trim()));
  r.ok(incoerenti.length === 0, incoerenti.length
    ? `eta' in riga diversa da quella calcolata: ${incoerenti.join(', ')}`
    : "l'eta' in riga e' sempre quella calcolata dalle annate");

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

  // ── i gruppi non sono <section> ───────────────────────────────────────
  // section{padding:100px 24px} arriva dal CSS di sistema: un gruppo nascosto
  // dai filtri lascerebbe 144px di niente in mezzo all'elenco.
  r.ok(await page.$$eval('.co-realta', (hs) => hs.every((h) => h.tagName !== 'SECTION')),
    'i gruppi realta\' sono <div>, non <section> (la trappola del padding)');

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

  await ctx.close();
  return r;
};
