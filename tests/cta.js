// I blocchi misurati e il ponte dalle schede evento ai corsi (14/09/2026).
//
// Nati dall'analisi di Giovanni: le schede evento fanno il 77% dei clic del
// sito, e non si sapeva quanti di quelli poi arrivano altrove, ne' da quale
// blocco. Qui si provano le tre cose che si rompono in silenzio:
//
//   1. i blocchi portano `data-cta`, se no daop-track.js non li vede e i
//      report restano vuoti senza un errore da nessuna parte;
//   2. la riga "N corsi per bambini a X" consegna quello che promette:
//      corsi.html?comune= accende la tendina e mostra le card di quel comune;
//   3. vista e clic arrivano a gtag con i parametri giusti, la vista una volta
//      sola e mai prima del consenso.
//
// NESSUN CONTEGGIO E' UNA PROVA. Il numero scritto sulle schede viene
// dall'indice della notte prima (genera_eventi gira prima di genera_corsi),
// quindi confrontarlo con corsi.html sarebbe rosso per un giro ogni volta che
// un corso entra o esce - cioe' quando il sito fa la cosa giusta. E' la prova
// delle quattro porte, gia' pagata: il disallineamento si stampa come nota.
'use strict';

const fs = require('fs');
const path = require('path');
const { apri, esito, RADICE } = require('./_aiuto');

const LINK_COMUNE = /href="\/corsi\.html\?comune=([^"#]*)#co-lista">(\d+) corsi per bambini/g;
const LINK_PROV = /href="\/corsi\.html#co-lista">(\d+) corsi per bambini in provincia/g;

function schede(dir) {
  const out = [];
  for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, f.name);
    if (f.isDirectory()) out.push(...schede(p));
    else if (f.name.endsWith('.html') && !f.name.startsWith('box-')) out.push(p);
  }
  return out;
}

module.exports = async function cta(browser) {
  const r = esito();

  // ── 1. i blocchi sono marcati ─────────────────────────────────────────
  r.titolo('eventi/ — blocchi misurati e link ai corsi');
  const file = schede(path.join(RADICE, 'eventi'));
  const corsiHtml = fs.readFileSync(path.join(RADICE, 'corsi.html'), 'utf8');
  const perCitta = {};
  let totCorsi = 0;
  for (const t of corsiHtml.match(/<article class="event-card[^>]*>/g) || []) {
    const m = /data-city="([^"]*)"/.exec(t);
    if (!m) continue;
    totCorsi++;
    perCitta[m[1]] = (perCitta[m[1]] || 0) + 1;
  }

  let vicini = 0, ginetto = 0, conCorsi = 0;
  const senzaMarca = [], note = [], malformati = [];
  let cavia = null, caviaSenzaCorsi = null;
  for (const p of file) {
    const html = fs.readFileSync(p, 'utf8');
    const rel = path.relative(RADICE, p).replace(/\\/g, '/');
    for (const t of html.match(/<section class="ev-vicini"[^>]*>/g) || []) {
      vicini++;
      if (!t.includes('data-cta="vicini"')) senzaMarca.push(rel + ' (vicini)');
    }
    // L'attributo intero, non il nome secco: GINETTO_CSS e' incollata nel
    // <style> di ogni pagina, e un includes sul nome direbbe "c'e'" ovunque.
    for (const t of html.match(/<(aside|section) class="(ev-ginetto-alto|bg-cream ev-ginetto)"[^>]*>/g) || []) {
      ginetto++;
      if (!t.includes('data-cta="ginetto"')) senzaMarca.push(rel + ' (ginetto)');
    }
    let trovato = false;
    for (const m of html.matchAll(LINK_COMUNE)) {
      trovato = true;
      const n = Number(m[2]);
      if (!m[1] || !(n > 0)) malformati.push(rel);
      else if (perCitta[m[1]] !== n) {
        note.push(`${rel}: promette ${n} corsi a ${m[1]}, corsi.html ne ha ${perCitta[m[1]] || 0}`);
      }
    }
    for (const m of html.matchAll(LINK_PROV)) {
      trovato = true;
      if (Number(m[1]) !== totCorsi) {
        note.push(`${rel}: promette ${m[1]} corsi in provincia, corsi.html ne ha ${totCorsi}`);
      }
    }
    if (trovato) {
      conCorsi++;
      // La cavia per il clic: una scheda con il link a un COMUNE, cosi' la
      // prova del filtro e quella del tracciamento guardano la stessa riga.
      if (!cavia && /\?comune=/.test(html) && html.includes('data-cta="ginetto"')
          && html.includes('data-cta="vicini"')) cavia = rel;
    } else if (!caviaSenzaCorsi && html.includes('data-cta="vicini"')) {
      caviaSenzaCorsi = rel;
    }
  }
  r.ok(vicini > 0 && senzaMarca.length === 0,
    senzaMarca.length
      ? `blocchi senza data-cta: ${senzaMarca.slice(0, 5).join(', ')}`
      : `${vicini} blocchi "altri eventi" e ${ginetto} di Ginetto, tutti marcati`);
  r.ok(malformati.length === 0,
    malformati.length ? `link ai corsi senza comune o senza numero: ${malformati.slice(0, 5).join(', ')}`
      : `${conCorsi} pagine con il link ai corsi, tutti col comune e il numero`);
  if (note.length) {
    console.log(`  nota ${note.length} numeri diversi da corsi.html (indice di ieri?): `
      + note.slice(0, 3).join(' | '));
  }

  // ── 2. il link consegna quello che promette ───────────────────────────
  r.titolo('corsi.html?comune= — la tendina accesa dal link');
  const citta = Object.keys(perCitta).sort((a, b) => perCitta[b] - perCitta[a])[0];
  if (citta) {
    const a = await apri(browser, `corsi.html?comune=${citta}#co-lista`, 412);
    const s = await a.page.evaluate((c) => {
      const sel = document.querySelector('[data-campo="citta"]');
      const card = [...document.querySelectorAll('.event-card[data-city]')];
      const lista = document.getElementById('co-lista');
      return {
        valore: sel && sel.value,
        visibili: card.filter((x) => !x.classList.contains('is-hidden')).length,
        diQuelComune: card.filter((x) => x.dataset.city === c).length,
        estranei: card.filter((x) => !x.classList.contains('is-hidden') && x.dataset.city !== c).length,
        conteggio: (document.getElementById('co-count') || {}).textContent || '',
        top: lista ? lista.getBoundingClientRect().top : null,
        alto: innerHeight,
      };
    }, citta);
    r.ok(s.valore === citta, `?comune=${citta} accende la tendina (vale ${JSON.stringify(s.valore)})`);
    r.ok(s.visibili === s.diQuelComune && s.estranei === 0 && s.visibili > 0,
      `restano le ${s.diQuelComune} card di ${citta}: visibili ${s.visibili}, di altri comuni ${s.estranei}`);
    r.ok(s.conteggio.startsWith(String(s.diQuelComune) + ' '),
      `il contatore dice lo stesso numero ("${s.conteggio}")`);
    r.ok(s.top !== null && s.top >= 0 && s.top < s.alto,
      `si atterra sull'elenco, non sull'intestazione (a ${Math.round(s.top)}px)`);
    await a.ctx.close();

    // Un comune che stanotte ha perso i suoi corsi: pagina intera, non vuota.
    const b = await apri(browser, 'corsi.html?comune=comune-che-non-esiste', 412);
    const t = await b.page.evaluate(() => ({
      valore: (document.querySelector('[data-campo="citta"]') || {}).value,
      nascoste: document.querySelectorAll('.event-card.is-hidden').length,
    }));
    r.ok(t.valore === 'all' && t.nascoste === 0,
      `un comune sconosciuto apre la pagina intera (tendina ${JSON.stringify(t.valore)}, ${t.nascoste} nascoste)`);
    await b.ctx.close();
  } else {
    r.ok(false, 'corsi.html senza card con data-city: il filtro non si puo\' provare');
  }

  // ── 3. vista e clic arrivano a gtag ───────────────────────────────────
  r.titolo('daop-track.js — internal_cta_view e internal_cta_click');
  const pagina = cavia || caviaSenzaCorsi;
  if (!pagina) {
    r.ok(false, 'nessuna scheda con il blocco "altri eventi": il tracciamento non si puo\' provare');
    return r;
  }
  if (!cavia) console.log('  nota nessuna scheda con il link a un comune: provo il clic su un altro link');
  const spia = () => { window.addEventListener('click', (e) => e.preventDefault(), true); };
  const c = await apri(browser, pagina, 412, spia);
  const pg = c.page;
  // Il banner dei cookie copre il fondo dello schermo: qui si prova il
  // tracciamento, non il banner. Il consenso resta SPENTO per il primo giro.
  await pg.evaluate(() => {
    const ban = document.getElementById('daop-cookie-banner');
    if (ban) ban.remove();
    window.__ga = [];
    window.daopConsensoAnalytics = false;
    window.gtag = function () { window.__ga.push([].slice.call(arguments)); };
  });
  const viste = (id) => pg.evaluate((i) => window.__ga.filter(
    (e) => e[1] === 'internal_cta_view' && e[2] && e[2].cta_id === i).map((e) => e[2]), id);
  const vai = async (sel) => {
    await pg.evaluate(() => window.scrollTo(0, 0));
    await pg.waitForTimeout(250);
    await pg.evaluate((s) => document.querySelector(s).scrollIntoView({ block: 'center' }), sel);
    await pg.waitForTimeout(400);
  };

  await vai('[data-cta="vicini"]');
  r.ok((await viste('vicini')).length === 0, 'senza consenso la vista non parte');

  await pg.evaluate(() => { window.daopConsensoAnalytics = true; });
  await vai('[data-cta="vicini"]');
  const v1 = await viste('vicini');
  r.ok(v1.length === 1, `dopo il consenso la vista arriva al passaggio dopo (${v1.length})`);
  r.ok(!!(v1[0] && v1[0].page_path && v1[0].event_city),
    `la vista porta pagina e comune (${JSON.stringify(v1[0] || {})})`);
  await vai('[data-cta="vicini"]');
  r.ok((await viste('vicini')).length === 1, 'ripassando sul blocco la vista non si ripete');

  const sel = cavia ? '[data-cta="vicini"] a[href^="/corsi.html?comune="]'
    : '[data-cta="vicini"] .ev-vic-all a[href^="/"]';
  const href = await pg.evaluate((s) => {
    const a = document.querySelector(s);
    window.__ga = [];
    a.click();
    return a.getAttribute('href');
  }, sel);
  const clic = await pg.evaluate(() => window.__ga.filter((e) => e[1] === 'internal_cta_click').map((e) => e[2]));
  r.ok(clic.length === 1, `un clic nel blocco = un internal_cta_click (${clic.length})`);
  const k = clic[0] || {};
  r.ok(k.cta_id === 'vicini' && k.destination_url === href,
    `il clic dice blocco e destinazione (${k.cta_id} -> ${k.destination_url})`);
  if (cavia) r.ok(k.destination_area === 'corsi', `destination_area del link ai corsi: ${k.destination_area}`);

  // Ginetto esce dal sito: resta `apri_ginetto`, con in piu' il blocco.
  if (await pg.locator('[data-cta="ginetto"] a[href*="ginettoapp.it"]').count()) {
    await vai('[data-cta="ginetto"]');
    // La vista si legge PRIMA del clic: il clic svuota il registro.
    r.ok((await viste('ginetto')).length === 1, 'la vista di Ginetto arriva');
    await pg.evaluate(() => {
      window.__ga = [];
      document.querySelector('[data-cta="ginetto"] a[href*="ginettoapp.it"]').click();
    });
    const g = await pg.evaluate(() => window.__ga.map((e) => [e[1], e[2] && e[2].cta_id]));
    r.ok(g.some((e) => e[0] === 'apri_ginetto' && e[1] === 'ginetto')
      && !g.some((e) => e[0] === 'internal_cta_click'),
      `Ginetto: apri_ginetto col blocco, nessun clic interno (${JSON.stringify(g)})`);
  }

  // Un link interno FUORI dai blocchi resta affidato ai page_view.
  await pg.evaluate(() => {
    window.__ga = [];
    const a = [...document.querySelectorAll('a[href^="/"]')].find((x) => !x.closest('[data-cta]'));
    if (a) a.click();
  });
  r.ok((await pg.evaluate(() => window.__ga.filter((e) => e[1] === 'internal_cta_click').length)) === 0,
    'un link interno fuori dai blocchi non produce internal_cta_click');
  await c.ctx.close();
  return r;
};
