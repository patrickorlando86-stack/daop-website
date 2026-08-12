// /luoghi.html: l'elenco filtrabile dei posti.
//
// Quello che si prova qui non e' "la pagina si apre", e' che reggano le tre
// decisioni su cui e' costruita, che sono anche le tre che qualcuno smonterebbe
// per distrazione:
//
//   1. la riga e' un <details>, quindi funziona senza JavaScript;
//   2. un gruppo comune svuotato dai filtri si porta via la sua intestazione;
//   3. il premium AGGIUNGE ma non RIORDINA - l'ordine resta alfabetico.
//
// La terza e' l'unica che vale anche come impegno verso chi legge (e verso
// l'art. 22 del Codice del consumo), quindi si controlla sull'output vero: se
// un giorno qualcuno ordinasse l'elenco per "premium prima", questa prova
// diventa rossa.
'use strict';

const { apri, esito } = require('./_aiuto');

const visibili = (page) => page.locator('.lg-row[data-cat]:not([hidden])').count();

module.exports = async function luoghi(browser) {
  const r = esito();

  r.titolo('luoghi.html — telefono 412px');
  let { ctx, page } = await apri(browser, 'luoghi.html', 412);
  const tot = await page.locator('.lg-row[data-cat]').count();
  r.ok(tot > 0, `${tot} luoghi in pagina`);

  // ── senza JavaScript la riga si apre lo stesso ────────────────────────
  r.ok(await page.evaluate(() =>
    [...document.querySelectorAll('.lg-row')].every((d) => d.tagName === 'DETAILS')),
    'ogni riga e\' un <details>: si apre anche senza JS');
  await page.locator('.lg-row summary').first().click();
  await page.waitForTimeout(200);
  r.ok(await page.locator('.lg-row').first().evaluate((d) => d.open),
    'la riga si apre al tocco');
  r.ok((await page.locator('.lg-row').first().locator('.lg-body').innerText()).trim().length > 20,
    'aperta, la riga dice qualcosa');
  await page.locator('.lg-row summary').first().click();
  await page.waitForTimeout(150);

  // ── la categoria si scrive, non solo si colora ────────────────────────
  r.ok((await page.locator('.lg-cat').first().textContent()).trim().length > 0,
    'la categoria si legge in riga, non e\' solo un colore');

  if (!(await page.locator('#lg-toolbar').count())) {
    r.ok(tot < 12, `niente barra filtri con ${tot} luoghi (sotto la soglia)`);
    await ctx.close();
    return r;
  }

  r.ok(await visibili(page) === tot, `a riposo si vedono tutti: ${tot}`);
  r.ok((await page.textContent('#lg-count')).trim() === '', 'a riposo il conteggio resta muto');
  r.ok(await page.locator('#lg-toolbar').evaluate((b) => b.offsetHeight) <= 130,
    'la barra filtri sta compatta sul telefono');

  // Una tendina che offre solo "tutti" non si stampa: e' un comando che non fa
  // niente. Due voci (tutti + una scelta) sono un comando vero, quindi la
  // soglia e' >1, non >2.
  r.ok(await page.evaluate(() =>
    [...document.querySelectorAll('#lg-toolbar .ev-select')]
      .every((s) => s.options.length > 1)),
    'nessuna tendina senza una scelta da fare');

  // ── i filtri ──────────────────────────────────────────────────────────
  const cat = await page.$eval('#lg-toolbar [data-campo="cat"]', (s) => s.options[1].value);
  await page.selectOption('#lg-toolbar [data-campo="cat"]', cat);
  await page.waitForTimeout(250);
  const n = await visibili(page);
  r.ok(n > 0 && n < tot, `filtro tipo di luogo "${cat}": ${n}/${tot}`);
  r.ok(await page.evaluate((c) =>
    [...document.querySelectorAll('.lg-row[data-cat]:not([hidden])')]
      .every((l) => l.dataset.cat === c), cat), 'restano solo le righe del tipo scelto');
  r.ok(/\d+ luogh?[io] con questi filtri/.test(await page.textContent('#lg-count')),
    'il conteggio compare quando si filtra');

  // Il guasto che si vede solo filtrando: il nome di un comune rimasto in aria
  // sopra il vuoto.
  r.ok(await page.evaluate(() =>
    [...document.querySelectorAll('.lg-grp')]
      .every((g) => g.hidden === !g.querySelector('.lg-row[data-cat]:not([hidden])'))),
    'i gruppi comune rimasti vuoti spariscono con la loro intestazione');

  const prov = await page.locator('#lg-toolbar [data-campo="prov"]');
  if (await prov.count()) {
    const p = await prov.evaluate((s) => s.options[1].value);
    await page.selectOption('#lg-toolbar [data-campo="prov"]', p);
    await page.waitForTimeout(250);
    r.ok(await page.evaluate((a) =>
      [...document.querySelectorAll('.lg-row[data-cat]:not([hidden])')]
        .every((l) => l.dataset.cat === a.c && l.dataset.prov === a.p), { c: cat, p }),
      'i due filtri si sommano');
    await page.selectOption('#lg-toolbar [data-campo="prov"]', 'all');
  }

  // "Se piove": i misto restano in tutte e due le risposte, per scelta.
  const pioggia = await page.locator('#lg-toolbar [data-campo="riparo"]');
  if (await pioggia.count()) {
    await page.selectOption('#lg-toolbar [data-campo="cat"]', 'all');
    await page.selectOption('#lg-toolbar [data-campo="riparo"]', 'chiuso');
    await page.waitForTimeout(250);
    r.ok(await page.evaluate(() =>
      [...document.querySelectorAll('.lg-row[data-cat]:not([hidden])')]
        .every((l) => l.dataset.riparo === 'chiuso' || l.dataset.riparo === 'misto')),
      'con "al chiuso" restano i chiusi e i misti, non gli aperti');
    await page.selectOption('#lg-toolbar [data-campo="riparo"]', 'all');
  }

  await page.fill('#lg-q', 'zzzznientedeltutto');
  await page.waitForTimeout(300);
  r.ok(await visibili(page) === 0, 'ricerca senza risultati: nessuna riga');
  r.ok(!(await page.locator('#lg-vuoto').evaluate((n) => n.hidden)),
    'compare il messaggio "nessun luogo con questi filtri"');
  await page.click('#lg-reset');
  await page.waitForTimeout(300);
  r.ok(await visibili(page) === tot, '"azzera i filtri" li fa tornare tutti');
  r.ok(await page.locator('#lg-vuoto').evaluate((n) => n.hidden), 'il messaggio sparisce');
  await ctx.close();

  // ── le convenzioni che qualcuno smonterebbe per distrazione ───────────
  r.titolo('luoghi.html — convenzioni');
  ({ ctx, page } = await apri(browser, 'luoghi.html', 412));

  r.ok(await page.evaluate(() =>
    getComputedStyle(document.querySelector('.lg-row')).contentVisibility === 'auto'),
    'content-visibility:auto sulle righe: e\' la voce piu\' pesante della pagina');

  // Il premium aggiunge, non riordina. Se l'elenco fosse ordinato per "chi
  // paga prima" questa prova diventa rossa - ed e' anche quello che il blocco
  // #come-ordiniamo promette a chi legge.
  r.ok(await page.locator('#come-ordiniamo').count() === 1,
    'la pagina dichiara come e\' ordinata (art. 22 Codice del consumo)');
  r.ok(await page.evaluate(() => {
    const norm = (s) => s.trim().toLowerCase().normalize('NFD').replace(/[^a-z0-9 ]/g, '');
    return [...document.querySelectorAll('.lg-grp')].every((g) => {
      const nomi = [...g.querySelectorAll('.lg-row[data-cat] .lg-nome')].map((n) => norm(n.textContent));
      return nomi.every((v, i) => i === 0 || nomi[i - 1] <= v);
    });
  }), 'dentro ogni comune l\'ordine e\' alfabetico: nessuna riga comprata sale');
  r.ok(await page.evaluate(() => {
    const prem = [...document.querySelectorAll('.lg-row.is-prem')];
    // Fuori dalla vetrina dichiarata, una scheda curata non sta mai in cima al
    // suo gruppo per il fatto di essere curata: sta dove la mette l'alfabeto.
    return prem.every((p) => p.closest('.lg-vetrina') || p.closest('.lg-grp'));
  }), 'le schede curate stanno nell\'elenco, non sopra di esso');

  // Le miniature: negli elenchi non ci vanno immagini remote per riga. E' il
  // conto della banda gia' sbagliato una volta con le locandine.
  r.ok(await page.evaluate(() =>
    [...document.querySelectorAll('.lg-row:not(.is-prem) img')].length === 0),
    'nessuna immagine nelle righe non curate: 173 foto in elenco sono banda buttata');

  // Il link diretto a un luogo deve aprire la riga, non lasciarla chiusa.
  const id = await page.locator('.lg-row').nth(5).getAttribute('id');
  await page.evaluate((h) => { location.hash = h; }, id);
  await page.waitForTimeout(400);
  r.ok(await page.locator(`#${id}`).evaluate((d) => d.open),
    `l'ancora #${id} apre la riga`);
  await ctx.close();

  return r;
};
