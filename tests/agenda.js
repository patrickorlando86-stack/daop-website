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

  // Prestazioni: due convenzioni che si smontano per distrazione.
  r.ok(await page.locator('.event-card').nth(200)
    .evaluate((c) => getComputedStyle(c).contentVisibility) === 'auto',
    'content-visibility:auto sulle schede');
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
  const id = await page.locator('.event-card').nth(30).getAttribute('id');
  await page.evaluate((x) => { location.hash = x; }, id);
  await page.waitForTimeout(500);
  r.ok(await page.evaluate((x) => !document.getElementById(x).querySelector('.ev-det').hidden, id),
    'un\'ancora #ev- apre la riga puntata');
  r.ok(await page.evaluate((x) => {
    const a = document.getElementById(x).querySelector('.ev-gcal');
    return !a || a.href.includes('&text=');
  }, id), 'arrivando da un\'ancora il link calendario risulta compilato');
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
