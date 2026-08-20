// eventi.html — le parti che vivono di JavaScript e che valida_jsonld.py non
// puo' vedere: righe che si aprono, link calendario ricostruito al volo,
// ricerca, filtri, vista calendario, ancore #ev-.
'use strict';

const { apri, esito } = require('./_aiuto');

module.exports = async function agenda(browser) {
  const r = esito();

  // ── telefono ──────────────────────────────────────────────────────────
  r.titolo('eventi.html — telefono 412px');
  let { ctx, page } = await apri(browser, 'eventi.html', 412);

  const comuni = page.locator('.ev-comuni-box');
  if (await comuni.count()) {
    r.ok(await comuni.evaluate((d) => !d.open), '"Vai al comune" e\' chiuso sul telefono');
  }

  const prima = page.locator('.event-card').first();
  r.ok(await prima.locator('.ev-det').evaluate((d) => d.hidden), 'il dettaglio parte chiuso');

  // Il link calendario nell'HTML e' la sola base: i campi li mette il JS
  // all'apertura della riga. Se qualcuno rimettesse l'URL intero nell'href
  // tornerebbero i 144 KB, e questa prova se ne accorge.
  const href0 = await prima.locator('.ev-gcal').getAttribute('href');
  r.ok(href0 === 'https://calendar.google.com/calendar/render?action=TEMPLATE',
    'href calendario e\' la sola base finche\' la riga e\' chiusa');

  await prima.locator('.ev-row').click();
  await page.waitForTimeout(150);
  r.ok(!(await prima.locator('.ev-det').evaluate((d) => d.hidden)), 'il dettaglio si apre al tocco');
  r.ok(await prima.locator('.ev-row').evaluate((b) => b.getAttribute('aria-expanded') === 'true'),
    'aria-expanded segue l\'apertura');

  const cal = await prima.locator('.ev-gcal').evaluate((a) =>
    Object.fromEntries(new URL(a.href).searchParams.entries()));
  const dati = await prima.evaluate((c) => ({
    start: c.dataset.start, end: c.dataset.end,
    nome: c.querySelector('.ev-name').textContent.trim(),
    descr: c.querySelector('.event-desc').textContent.trim(),
  }));
  r.ok(cal.text === dati.nome, 'calendario: il titolo e\' il nome dell\'evento');
  const fine = new Date(dati.end + 'T00:00:00');
  fine.setDate(fine.getDate() + 1);
  const isoFine = fine.getFullYear() + String(fine.getMonth() + 1).padStart(2, '0') +
                  String(fine.getDate()).padStart(2, '0');
  // Google vuole la fine ESCLUSIVA: il giorno dopo l'ultimo. Sbagliarlo
  // accorcia ogni sagra di un giorno nel calendario di chi la salva.
  r.ok(cal.dates === dati.start.replace(/-/g, '') + '/' + isoFine,
    `calendario: date ${cal.dates}, fine esclusiva`);
  r.ok(cal.details === dati.descr.slice(0, 900), 'calendario: descrizione presa dal DOM');
  r.ok(!!cal.location, 'calendario: il luogo c\'e\'');

  await prima.locator('.ev-row').click();
  await page.waitForTimeout(100);
  r.ok(await prima.locator('.ev-det').evaluate((d) => d.hidden), 'il dettaglio si richiude');

  const tot = await page.locator('.event-card').count();
  await page.fill('#ev-q', 'alessandria');
  await page.waitForTimeout(300);
  const visti = await page.locator('.event-card:not(.is-hidden)').count();
  r.ok(visti > 0 && visti < tot, `la ricerca restringe: ${visti}/${tot}`);
  r.ok(/\d+ eventi? in agenda/.test(await page.textContent('#events-count')), 'il contatore si aggiorna');
  await page.fill('#ev-q', '');
  await page.waitForTimeout(300);
  r.ok(await page.locator('.event-card:not(.is-hidden)').count() === tot,
    'svuotando la ricerca tornano tutte');

  await page.selectOption('#f-dove', 'cn');
  await page.waitForTimeout(300);
  const cn = await page.locator('.event-card:not(.is-hidden)').count();
  r.ok(cn > 0 && cn < tot, `filtro provincia: ${cn}/${tot}`);
  r.ok(await page.$eval('#f-dove', (s) => s.classList.contains('is-on')), 'la tendina attiva si evidenzia');
  await page.selectOption('#f-dove', 'all');
  await page.waitForTimeout(200);

  // Filtro "Weekend": una sagra che comincia venerdi' e arriva a domenica resta
  // (si confronta la sovrapposizione, non l'inizio), ma la sua sezione si chiama
  // ancora "venerdi'", e senza una riga che lo spieghi sembra un filtro rotto -
  // segnalato il 20/08/2026, "filtro weekend e vedo giovedi'". Il numero a
  // destra dell'intestazione, poi, e' quello scritto dal generatore: con un
  // filtro attivo diceva 13 dove se ne vedevano 8.
  await page.selectOption('#f-quando', 'weekend');
  await page.waitForTimeout(300);
  const sezioni = await page.$$eval('.ev-day:not(.is-hidden)', (gs) => gs.map((g) => ({
    giorno: g.dataset.day,
    nota: (g.querySelector('.ev-daynote') || {}).textContent || '',
    scritto: (g.querySelector('.ev-daycount') || {}).textContent || '',
    vivi: String(g.querySelectorAll('.event-card:not(.is-hidden)').length),
  })));
  r.ok(sezioni.every((s) => s.scritto === s.vivi),
    `col filtro attivo ogni giorno conta quello che mostra (${sezioni.length} sezioni)`);
  const sab = await page.evaluate(() => {
    const d = new Date(); d.setHours(0, 0, 0, 0);
    const g = d.getDay();
    const s = new Date(d); s.setDate(d.getDate() + (g === 0 ? -1 : 6 - g));
    return s.getFullYear() + '-' + String(s.getMonth() + 1).padStart(2, '0') +
           '-' + String(s.getDate()).padStart(2, '0');
  });
  r.ok(sezioni.every((s) => (s.giorno !== 'in-corso' && s.giorno < sab)
    ? /weekend/.test(s.nota) : s.nota === ''),
    `la nota spiega tutti e soli i giorni prima di sabato ${sab}`);
  await page.selectOption('#f-quando', 'all');
  await page.waitForTimeout(300);
  r.ok(await page.locator('.ev-daynote').count() === 0,
    'tolto il filtro, la nota sparisce');
  r.ok(await page.locator('.event-card:not(.is-hidden)').count() === tot,
    'tolto il filtro tornano tutte le schede');

  // Prestazioni: due convenzioni che si smontano per distrazione.
  // La scheda si prende in fondo all'elenco e non a un indice fisso: il 21/08/2026
  // la prova cercava la 201esima su un'agenda scesa a 199 eventi, e la run
  // notturna e' diventata rossa per il calendario, non per un difetto. Il numero
  // di eventi in agenda cala da solo a fine stagione: qualunque indice scritto a
  // mano e' una data di scadenza.
  r.ok(await page.locator('.event-card').nth(tot - 1)
    .evaluate((c) => getComputedStyle(c).contentVisibility) === 'auto',
    `content-visibility:auto sulle schede (l'ultima delle ${tot})`);
  r.ok(/^\d+px$/.test(await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue('--ev-sticky').trim())),
    '--ev-sticky viene misurata dopo il primo disegno');

  // Sul telefono non c'e' :hover: il colore di categoria dev'esserci comunque.
  const bordo = await prima.locator('.ev-row').evaluate((b) => getComputedStyle(b).borderLeftColor);
  r.ok(bordo !== 'rgba(0, 0, 0, 0)' && bordo !== 'transparent',
    'il bordo di categoria si vede senza hover');

  await page.click('#v-cal');
  await page.waitForTimeout(400);
  r.ok(await page.locator('.ev-cal-grid').count() === 1, 'la vista calendario disegna la griglia');
  r.ok(await page.locator('.ev-cal-day.has').count() > 0, 'il calendario segna i giorni pieni');
  await page.click('#v-agenda');
  await page.waitForTimeout(300);

  // content-visibility non deve impedire di arrivare a una scheda lontana.
  const id = await page.locator('.event-card').nth(Math.min(30, tot - 1)).getAttribute('id');
  await page.evaluate((x) => { location.hash = x; }, id);
  await page.waitForTimeout(500);
  r.ok(await page.evaluate((x) => !document.getElementById(x).querySelector('.ev-det').hidden, id),
    'un\'ancora #ev- apre la riga puntata');
  r.ok(await page.evaluate((x) => {
    const a = document.getElementById(x).querySelector('.ev-gcal');
    return !a || a.href.includes('&text=');
  }, id), 'arrivando da un\'ancora il link calendario risulta compilato');
  await ctx.close();

  // ── "Vicino a me" ─────────────────────────────────────────────────────
  // Si riapre la pagina con una spia sulla Geolocation API: la regola numero
  // uno e' che la posizione non si chieda da sola. Il resto si prova dal
  // ripiego "parti da un comune", che non ha bisogno di permessi ed e' la
  // stessa strada che percorre chi il permesso l'ha negato.
  r.titolo('eventi.html — vicino a me');
  ({ ctx, page } = await apri(browser, 'eventi.html', 412, () => {
    window.__geo = 0;
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition = function () { window.__geo++; };
    }
  }));

  r.ok(await page.evaluate(() => window.__geo) === 0,
    'la posizione NON si chiede al caricamento (serve un tocco)');

  const conCoord = await page.locator('.event-card[data-lat][data-lon]').count();
  const tutte = await page.locator('.event-card').count();
  r.ok(conCoord === tutte, `ogni riga porta le sue coordinate: ${conCoord}/${tutte}`);
  r.ok(await page.locator('#ev-geo').isVisible(), 'il controllo compare quando il JS c\'e\'');

  // L'ordine del documento prima di toccare qualsiasi cosa: serve piu' sotto a
  // dimostrare che il raggio non riordina niente.
  const ordine0 = await page.evaluate(() =>
    Array.from(document.querySelectorAll('.event-card')).map((c) => c.id));

  // L'elenco dei comuni si costruisce all'apertura, non al caricamento.
  r.ok(await page.locator('#ev-geo-list option').count() === 0,
    'l\'elenco dei comuni non si costruisce al caricamento');
  await page.locator('#ev-geo-alt').click();
  await page.waitForTimeout(200);
  r.ok(await page.locator('#ev-geo-list option').count() > 0,
    'l\'elenco dei comuni si costruisce alla prima apertura');

  // Un comune con eventi: gradini, conteggi, e il filtro che filtra davvero.
  const primoComune = await page.locator('#ev-geo-list option').first().getAttribute('value');
  await page.fill('#ev-geo-q', primoComune);
  await page.waitForTimeout(350);
  r.ok((await page.locator('#ev-geo-from').textContent()).includes(primoComune),
    `il centro e' il comune scelto (${primoComune})`);

  const chip = page.locator('#ev-geo-chips button[aria-pressed="true"]');
  r.ok(await chip.count() === 1, 'un gradino solo e\' quello attivo');
  const attivo = parseInt(await chip.textContent(), 10);
  // Il gradino di partenza si sceglie sui dati: da un paese piccolo un raggio
  // stretto darebbe una pagina vuota, ed e' il difetto tipico di questi filtri.
  r.ok(await page.locator('.event-card:not(.is-hidden)').count() > 0,
    `il raggio di partenza (${attivo} km) non lascia la pagina vuota`);
  r.ok(/\(\d+\)/.test(await page.locator('#ev-geo-chips button').first().textContent()),
    'ogni gradino porta il suo conteggio: non si sceglie al buio');

  // La prova che conta: nessuna riga mostrata sta oltre il raggio, e ognuna
  // dichiara la propria distanza.
  const sbagliate = await page.evaluate((rag) => {
    const fuori = [];
    document.querySelectorAll('.event-card:not(.is-hidden)').forEach((c) => {
      const t = c.querySelector('.ev-km');
      if (!t) return fuori.push('riga senza distanza');
      const m = t.textContent.match(/a (\d+) km/);
      if (m && Number(m[1]) > rag) fuori.push(m[1] + ' km');
    });
    return fuori;
  }, attivo);
  r.ok(sbagliate.length === 0,
    `nessuna riga mostrata sta oltre il raggio (${sbagliate.slice(0, 3).join(', ') || 'ok'})`);

  // Il raggio filtra, non riordina: l'agenda e' un calendario e l'ordine di un
  // calendario e' la data (le righe "in corso" stanno in cima per gruppo, non
  // per data, quindi l'ordine giusto e' quello che il generatore ha scritto).
  // Le righe rimaste devono essere una sottosequenza di quell'ordine: se un
  // giorno qualcuno ordinasse per vicinanza, questa prova diventa rossa.
  const rimaste = await page.evaluate(() =>
    Array.from(document.querySelectorAll('.event-card:not(.is-hidden)')).map((c) => c.id));
  let k = -1;
  const inOrdine = rimaste.every((id) => {
    const i = ordine0.indexOf(id);
    if (i <= k) return false;
    k = i;
    return true;
  });
  r.ok(inOrdine && rimaste.length > 0,
    'il raggio filtra e non riordina: nessuna riga vicina scavalca le altre');

  // Un raggio stretto piu' una categoria stretta e' il modo piu' facile di
  // arrivare a zero: li' si deve dire dove sta la roba, non lasciare il vuoto.
  await page.selectOption('#f-tipo', 'laboratori');
  await page.waitForTimeout(300);
  if (await page.locator('.event-card:not(.is-hidden)').count() === 0) {
    const hint = await page.locator('#ev-geo-hint').textContent();
    r.ok(/Entro \d+ km/.test(hint),
      `a zero risultati dice dove guardare: "${hint}"`);
  }
  await page.selectOption('#f-tipo', 'all');
  await page.waitForTimeout(200);

  // Un comune che in agenda non c'e' deve dirlo, non restare muto.
  await page.fill('#ev-geo-q', 'Zzzznonesiste');
  await page.waitForTimeout(300);
  r.ok((await page.locator('#ev-geo-note').textContent()).includes('Nessun evento'),
    'un comune senza eventi lo dice invece di restare muto');

  // La ✕ rimette tutto com'era, distanze comprese.
  await page.fill('#ev-geo-q', primoComune);
  await page.waitForTimeout(300);
  await page.locator('#ev-geo-clear').click();
  await page.waitForTimeout(300);
  r.ok(await page.locator('.event-card:not(.is-hidden)').count() === tutte,
    'la ✕ rimette tutte le righe');
  r.ok(await page.locator('.ev-km').count() === 0, 'la ✕ toglie anche le distanze dalle righe');
  r.ok(await page.evaluate(() => window.__geo) === 0,
    'in tutto questo la posizione non e\' mai stata chiesta');
  await ctx.close();

  // ── desktop ───────────────────────────────────────────────────────────
  r.titolo('eventi.html — desktop 1280px');
  ({ ctx, page } = await apri(browser, 'eventi.html', 1280));
  if (await page.locator('.ev-comuni-box').count()) {
    r.ok(await page.$eval('.ev-comuni-box', (d) => d.open), '"Vai al comune" resta aperto su desktop');
    r.ok(await page.locator('.ev-comuni-box .ev-comuni a').count() > 0,
      'i link ai comuni sono nel DOM');
  }
  await ctx.close();

  return r;
};
