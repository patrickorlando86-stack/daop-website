// Impalcatura condivisa delle prove di fumo.
//
// Il sito e' statico e si apre da file://, quindi non serve un server: basta
// impedire ogni richiesta verso l'esterno. Le locandine stanno su Supabase e
// in CI non vanno scaricate - 300 immagini per una prova che non le guarda -
// quindi al loro posto arriva un pixel, che tiene i tempi bassi e rende la
// prova indipendente dal fatto che il bucket risponda.
'use strict';

const path = require('path');
const { chromium } = require('playwright');

const RADICE = path.resolve(__dirname, '..');

// Un PNG 1x1: sostituisce ogni locandina.
const PIXEL = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64');

async function avvia() {
  return chromium.launch({
    // In CI Playwright usa il browser che si e' installato da solo. In un
    // ambiente che ne ha gia' uno pronto si passa da CHROMIUM_PATH, cosi' la
    // prova non scarica niente.
    executablePath: process.env.CHROMIUM_PATH || undefined,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
}

async function apri(browser, file, larghezza = 412) {
  const ctx = await browser.newContext({
    viewport: { width: larghezza, height: 915 },
    deviceScaleFactor: 2,
    isMobile: larghezza < 700,
    hasTouch: larghezza < 700,
  });
  const page = await ctx.newPage();
  await page.route('**/*', (route) => {
    const u = route.request().url();
    if (u.startsWith('file://')) return route.continue();
    if (/\.(jpe?g|png|webp|avif|gif)(\?|$)/i.test(u)) {
      return route.fulfill({ status: 200, contentType: 'image/png', body: PIXEL });
    }
    return route.abort();
  });
  await page.goto('file://' + path.join(RADICE, file), { waitUntil: 'load', timeout: 120000 });
  await page.waitForTimeout(400);
  return { ctx, page };
}

// Raccoglitore dei risultati: conta e stampa, senza far uscire il processo a
// meta' - chi chiama decide alla fine.
function esito() {
  const stato = { passati: 0, falliti: [] };
  stato.ok = (cond, msg) => {
    if (cond) {
      stato.passati++;
      console.log('  ok   ' + msg);
    } else {
      stato.falliti.push(msg);
      console.log('  FALLITO  ' + msg);
    }
  };
  stato.titolo = (t) => console.log('\n' + t);
  return stato;
}

module.exports = { avvia, apri, esito, RADICE };
