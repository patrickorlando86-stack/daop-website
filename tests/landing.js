// Pagine di intenzione: /eventi/oggi.html, /eventi/weekend.html e le
// sagre-provincia-*. Filtri, e le due trappole che il filtro deve gestire
// (titoli orfani e blocchi che non si filtrano).
'use strict';

const { apri, esito } = require('./_aiuto');

const visibili = (page) => page.locator('.ev-wrap li[data-category]:not([hidden])').count();

// Le sagre-provincia-* mostrano in coda anche il RESTO dell'agenda della
// provincia (laboratori, cultura, spettacoli, musica, sport). Non e' un
// cambio di identita' della pagina: e' distribuzione, e le prove qui sotto
// difendono le tre cose che si romperebbero rifacendola a mente.
// Il selettore dei DUE ELENCHI COMPLEMENTARI, cioe' il calendario delle sagre
// e "Non solo sagre". Esclude la sezione "Eventi per bambini", che dal
// 03/09/2026 sta in fondo e NON e' un terzo insieme: e' una vista sulle stesse
// schede (e_per_bambini() le ripesca da tutte e due). Senza questa esclusione
// le prove 2 e 4 qui sotto chiederebbero che i due elenchi siano gli unici in
// pagina, che non e' l'invariante - l'invariante e' che restino complementari
// FRA LORO, e la prova 6 dice l'altra meta': la vista non inventa niente.
const DUE = '.ev-wrap li[data-category]:not(.com-bimbi li)';

async function provaNonSoloSagre(r, page, prov) {
  const righe = await page.locator(DUE).count();
  const nonSagre = await page.locator(`${DUE}:not([data-category=feste])`).count();

  // 1) La pagina resta una pagina di SAGRE. E' la query che vince (405 clic e
  //    posizione 6,86 su Cuneo nell'export del 26/08/2026): il blocco in coda
  //    aggiunge contenuto, non riscrive l'identita' della pagina. La
  //    tentazione da fermare e' "gia' che ci siamo chiamiamola eventi-".
  r.ok(/^Sagre e feste in provincia di /.test(await page.$eval('h1', (h) => h.textContent.trim())),
    `${prov}: l'H1 resta quello delle sagre`);
  r.ok(/sagre/i.test(await page.title()), `${prov}: "sagre" resta nel <title>`);
  r.ok(/\/sagre-provincia-/.test(await page.$eval('link[rel=canonical]', (l) => l.href)),
    `${prov}: il canonical non si muove`);

  if (!nonSagre) {
    // Fuori stagione una provincia puo' non avere altro che sagre: la sezione
    // non si stampa, e non e' un guasto.
    r.ok(true, `${prov}: nessun evento non-sagra in agenda, sezione assente`);
    return;
  }

  // 2) Nessun evento sta in tutti e due gli elenchi. L'invariante NON e'
  //    "ogni href compare una volta sola": una manifestazione di tre giorni ha
  //    tre righe che puntano alla stessa scheda, ed e' giusto - il calendario
  //    delle sagre lo fa da sempre. Quello che i due filtri complementari
  //    devono garantire e' che la stessa scheda non finisca sopra E sotto:
  //    se un giorno il secondo elenco smettesse di essere il complemento del
  //    primo, la pagina direbbe due volte la stessa cosa con due titoli che si
  //    contraddicono ("sagre" e "che non sono sagre").
  const attraverso = await page.evaluate((sel) => {
    const m = new Map();
    document.querySelectorAll(sel).forEach((l) => {
      const a = l.querySelector('a.com-go');
      if (!a) return;
      const h = a.getAttribute('href');
      (m.get(h) || m.set(h, new Set()).get(h)).add(l.dataset.category === 'feste');
    });
    return [...m].filter(([, s]) => s.size > 1).map(([h]) => h);
  }, DUE);
  r.ok(attraverso.length === 0,
    `${prov}: nessuna scheda compare sopra e sotto insieme (${righe} righe)`
    + (attraverso.length ? ': ' + attraverso.slice(0, 3).join(', ') : ''));

  // 3) LA REGRESSIONE VERA. La tendina delle categorie si costruisce
  //    dall'elenco che _landing_filtri riceve: passandogli le sole sagre
  //    resterebbe con una voce sola, e una tendina da una voce non si stampa
  //    affatto - cioe' il filtro sparirebbe con settanta righe in pagina e
  //    cinque categorie da separare. Non si legge nell'HTML: si vede solo
  //    confrontando le opzioni con le righe.
  if (righe >= 12) {
    const mancanti = await page.evaluate((s) => {
      const sel = document.getElementById('lan-tipo');
      if (!sel) return ['(la tendina delle categorie non viene stampata)'];
      const opz = new Set([...sel.options].map((o) => o.value));
      const cat = new Set([...document.querySelectorAll(s)].map((l) => l.dataset.category));
      return [...cat].filter((c) => !opz.has(c));
    }, DUE);
    r.ok(mancanti.length === 0,
      `${prov}: la tendina conosce tutte le categorie in pagina${mancanti.length ? ': manca ' + mancanti.join(', ') : ''}`);
  }

  // 4) Le sagre restano il contenuto principale: il blocco in coda sta DOPO
  //    l'ultima riga del calendario, se no la pagina si apre su quello che
  //    non e' la sua query.
  r.ok(await page.evaluate((sel) => {
    const li = [...document.querySelectorAll(sel)];
    const ultimaSagra = li.map((l, i) => [l.dataset.category, i])
      .filter(([c]) => c === 'feste').pop();
    const primaAltra = li.findIndex((l) => l.dataset.category !== 'feste');
    return !ultimaSagra || primaAltra === -1 || primaAltra > ultimaSagra[1];
  }, DUE), `${prov}: le ${righe - nonSagre} sagre stanno prima delle ${nonSagre} altre`);

  // 6) LA SEZIONE "EVENTI PER BAMBINI" E' UNA VISTA, NON UN TERZO INSIEME.
  //    E' la prova che tiene onesto il blocco nato il 03/09/2026: ogni riga
  //    che compare li' deve esistere anche in uno dei due elenchi sopra. Se un
  //    domani quella sezione cominciasse a pescare da un'altra parte — dallo
  //    storico, da un'altra provincia — la pagina prometterebbe nell'H2 degli
  //    eventi che il suo stesso calendario non contiene, e nessun'altra prova
  //    se ne accorgerebbe.
  //
  //    NON si conta quante sono: e' il numero che cambia ogni notte, ed e'
  //    l'inciampo gia' pagato sei volte in questo repo (la copertura delle
  //    coordinate, il conteggio delle quattro porte, il robots delle pagine
  //    realta'). Si controlla il RAPPORTO fra due insiemi, che non ha una
  //    taglia giusta.
  const bimbi = await page.evaluate((sel) => {
    const dentro = new Set([...document.querySelectorAll(sel)]
      .map((l) => (l.querySelector('a.com-go') || {}).getAttribute
        ? l.querySelector('a.com-go').getAttribute('href') : null)
      .filter(Boolean));
    const kids = [...document.querySelectorAll('.com-bimbi li[data-category]')]
      .map((l) => (l.querySelector('a.com-go') || {}).getAttribute
        ? l.querySelector('a.com-go').getAttribute('href') : null)
      .filter(Boolean);
    return { quanti: kids.length, estranei: kids.filter((h) => !dentro.has(h)) };
  }, DUE);
  if (bimbi.quanti) {
    r.ok(bimbi.estranei.length === 0,
      `${prov}: le ${bimbi.quanti} righe "per bambini" sono tutte negli elenchi sopra`
      + (bimbi.estranei.length ? ': estranee ' + bimbi.estranei.slice(0, 3).join(', ') : ''));
    r.ok(await page.evaluate(() => {
      const h2 = [...document.querySelectorAll('.ev-wrap h2')]
        .find((h) => /Eventi per bambini/.test(h.textContent));
      const ul = document.querySelector('.com-bimbi');
      if (!h2 || !ul) return false;
      // La sezione sta DOPO l'ultima riga dei due elenchi: sopra ci va quello
      // per cui la gente e' arrivata, che su questa pagina sono le sagre.
      const ultima = [...document.querySelectorAll(
        '.ev-wrap li[data-category]:not(.com-bimbi li)')].pop();
      return !ultima ||
        (ultima.compareDocumentPosition(h2) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
    }), `${prov}: "Eventi per bambini" sta dopo il calendario, non prima`);
    // E LA RIGA DEVE ESSERE ALTA COME LE ALTRE. Non e' pignoleria: la prima
    // versione di questo blocco (03/09/2026) usava la classe .com-kids, che
    // sta in COMUNE_CSS ed e' tarata sulla riga delle pagine comune. Le righe
    // qui le fa _landing_righe(), che ha un'altra forma: le due insieme
    // davano 332px per riga invece di 101, cioe' 3.981px per dodici righe,
    // con l'HTML perfettamente giusto e ogni altra prova verde.
    //
    // Si misura il RESO, non si legge il CSS — e' l'unico modo di vedere
    // questo genere di guasto, gia' pagato con la barra delle azioni alta
    // 915px e col crumb dei corsi a contrasto 1,07:1. Il confronto e' con le
    // righe degli altri elenchi della stessa pagina, non con un numero
    // scritto qui: 102px oggi sarebbe rosso al primo ritocco di stile.
    const alte = await page.evaluate(() => {
      const media = (sel) => {
        const li = [...document.querySelectorAll(sel)];
        if (!li.length) return 0;
        return li.reduce((n, l) => n + l.getBoundingClientRect().height, 0) / li.length;
      };
      return { bimbi: media('.com-bimbi li'),
               normali: media('.ev-wrap ul.com-ev:not(.com-bimbi) li') };
    });
    r.ok(alte.normali > 0 && Math.abs(alte.bimbi - alte.normali) < alte.normali * 0.25,
      `${prov}: le righe "per bambini" sono alte come le altre `
      + `(${Math.round(alte.bimbi)}px contro ${Math.round(alte.normali)}px)`);
  } else {
    r.ok(true, `${prov}: meno di 3 eventi per bambini, sezione assente (voluto)`);
  }

  // 5) Filtrando su una categoria non-sagra restano righe, e il titolo del
  //    blocco non resta orfano sopra il vuoto.
  if (await page.locator('#lan-tipo').count()) {
    const cat = await page.evaluate(() =>
      (document.querySelector('.ev-wrap li[data-category]:not([data-category=feste])') || {})
        .dataset.category);
    await page.selectOption('#lan-tipo', cat);
    await page.waitForTimeout(250);
    const n = await page.locator('.ev-wrap li[data-category]:not([hidden])').count();
    r.ok(n > 0 && n < righe, `${prov}: filtro "${cat}" ${n}/${righe}`);
    r.ok(await page.evaluate(() =>
      [...document.querySelectorAll('.ev-wrap h2')].every((h) => {
        if (h.hidden) return true;
        let n = h.nextElementSibling;
        while (n && n.tagName === 'P') n = n.nextElementSibling;
        return !n || !n.classList.contains('com-grp') || !n.hidden;
      })), `${prov}: nessun titolo resta orfano`);
    await page.selectOption('#lan-tipo', 'all');
    await page.waitForTimeout(200);
  }
}

module.exports = async function landing(browser) {
  const r = esito();

  // ── oggi ──────────────────────────────────────────────────────────────
  r.titolo('eventi/oggi.html — telefono 412px');
  let { ctx, page } = await apri(browser, 'eventi/oggi.html', 412);
  const tot = await page.locator('.ev-wrap li[data-category]').count();

  if (!(await page.locator('#lan-toolbar').count())) {
    // Sotto MIN_FILTRI la barra non si stampa: e' voluto, non un guasto.
    r.ok(tot < 12, `niente barra filtri con ${tot} eventi (sotto la soglia)`);
    await ctx.close();
    return r;
  }

  r.ok(await visibili(page) === tot, `a riposo si vedono tutti: ${tot}`);
  r.ok((await page.textContent('#lan-count')).trim() === '', 'a riposo il conteggio resta muto');

  if (await page.locator('#lan-tipo').count()) {
    const cat = await page.$eval('#lan-tipo', (s) => s.options[1].value);
    await page.selectOption('#lan-tipo', cat);
    await page.waitForTimeout(250);
    const n = await visibili(page);
    r.ok(n > 0 && n < tot, `filtro categoria "${cat}": ${n}/${tot}`);
    r.ok(await page.evaluate((c) =>
      [...document.querySelectorAll('.ev-wrap li[data-category]:not([hidden])')]
        .every((l) => l.dataset.category === c), cat), 'restano solo le righe della categoria scelta');
    r.ok(/\d+ eventi? con questi filtri/.test(await page.textContent('#lan-count')),
      'il conteggio compare quando si filtra');
    r.ok(await page.$eval('#lan-tipo', (s) => s.classList.contains('is-on')),
      'la tendina attiva si evidenzia');

    // Un gruppo svuotato sparisce, e con lui il suo titolo: su queste pagine i
    // titoli stanno PRIMA della sezione e fuori da essa, quindi resterebbero
    // sospesi sopra il vuoto.
    r.ok(await page.evaluate(() =>
      [...document.querySelectorAll('.ev-wrap .com-grp')]
        .filter((g) => g.querySelector('li[data-category]'))
        .every((g) => g.hidden === !g.querySelector('li[data-category]:not([hidden])'))),
      'i gruppi rimasti vuoti spariscono');
    r.ok(await page.evaluate(() =>
      [...document.querySelectorAll('.ev-wrap h2')].every((h) => {
        if (h.hidden) return true;
        let n = h.nextElementSibling;
        while (n && n.tagName === 'P') n = n.nextElementSibling;
        return !n || !n.classList.contains('com-grp') || !n.hidden;
      })), 'nessun titolo resta orfano sopra un gruppo nascosto');
    r.ok(await page.evaluate(() => {
      const p = document.querySelector('.ev-wrap > p');
      return p && !p.hidden;
    }), 'il paragrafo di apertura non viene mai nascosto');

    if (await page.locator('#lan-dove').count()) {
      const pr = await page.$eval('#lan-dove', (s) => s.options[1].value);
      await page.selectOption('#lan-dove', pr);
      await page.waitForTimeout(250);
      r.ok(await page.evaluate((a) =>
        [...document.querySelectorAll('.ev-wrap li[data-category]:not([hidden])')]
          .every((l) => l.dataset.category === a.c && l.dataset.province === a.p),
        { c: cat, p: pr }), 'i due filtri si sommano');
      await page.selectOption('#lan-dove', 'all');
    }
    await page.selectOption('#lan-tipo', 'all');
    await page.waitForTimeout(200);
  }

  await page.fill('#lan-q', 'zzzznientedeltutto');
  await page.waitForTimeout(300);
  r.ok(await visibili(page) === 0, 'ricerca senza risultati: nessuna riga');
  r.ok(!(await page.locator('#lan-nulla').evaluate((n) => n.hidden)),
    'compare il messaggio "non resta niente"');
  await page.click('#lan-reset');
  await page.waitForTimeout(300);
  r.ok(await visibili(page) === tot, '"azzera i filtri" le fa tornare tutte');
  r.ok(await page.locator('#lan-nulla').evaluate((n) => n.hidden), 'il messaggio sparisce');

  r.ok((await page.locator('.com-cat').first().textContent()).trim().length > 0,
    'la categoria si legge in riga');
  r.ok(await page.locator('#lan-toolbar').evaluate((b) => b.offsetHeight) <= 120,
    'la barra filtri sta compatta sul telefono');
  await ctx.close();

  // ── weekend ───────────────────────────────────────────────────────────
  r.titolo('eventi/weekend.html — telefono 412px');
  ({ ctx, page } = await apri(browser, 'eventi/weekend.html', 412));
  const totW = await page.locator('.ev-wrap li[data-category]').count();
  if (await page.locator('#lan-dove').count()) {
    const pr = await page.$eval('#lan-dove', (s) => s.options[1].value);
    await page.selectOption('#lan-dove', pr);
    await page.waitForTimeout(250);
    const n = await visibili(page);
    r.ok(n > 0 && n < totW, `filtro provincia "${pr}": ${n}/${totW}`);
  } else {
    r.ok(true, 'nessuna tendina provincia da provare su questa pagina');
  }
  await ctx.close();

  // ── sagre per provincia ───────────────────────────────────────────────
  r.titolo('sagre-provincia-alessandria.html — telefono 412px');
  ({ ctx, page } = await apri(browser, 'sagre-provincia-alessandria.html', 412));
  if (await page.locator('#lan-toolbar').count()) {
    r.ok(await page.locator('#lan-dove').count() === 0,
      'niente tendina provincia: la pagina E\' una provincia');
    const totS = await page.locator('.ev-wrap li[data-category]').count();
    await page.fill('#lan-q', 'acqui');
    await page.waitForTimeout(300);
    const n = await visibili(page);
    r.ok(n > 0 && n < totS, `ricerca per paese: ${n}/${totS}`);
    // L'elenco delle feste che tornano ogni anno non ha provincia ne'
    // categoria: filtrando non deve sparire.
    const anni = await page.locator('.com-anni li').count();
    if (anni) {
      r.ok(await page.locator('.com-anni li:not([hidden])').count() === anni,
        `le ${anni} feste ricorrenti restano visibili`);
    }
    // Il bottone "azzera" vive dentro il messaggio di elenco vuoto, che qui
    // non c'e': la ricerca ha trovato qualcosa. Si svuota il campo.
    await page.fill('#lan-q', '');
    await page.waitForTimeout(250);
  }
  await provaNonSoloSagre(r, page, 'Alessandria');
  await ctx.close();

  // Cuneo e' la provincia che ha fatto nascere il blocco: in agenda le sagre
  // sono una minoranza (16 su 74 il 29/08/2026), quindi qui la sezione "Non
  // solo sagre" pesa piu' del calendario sopra. Si prova a parte proprio per
  // questo - su Alessandria il difetto passerebbe quasi inosservato.
  r.titolo('sagre-provincia-cuneo.html — telefono 412px');
  ({ ctx, page } = await apri(browser, 'sagre-provincia-cuneo.html', 412));
  await provaNonSoloSagre(r, page, 'Cuneo');
  await ctx.close();

  // ── ferragosto ────────────────────────────────────────────────────────
  // Pagina stagionale: le prove qui sotto difendono le due cose che si
  // smontano per distrazione, e che si pagano un anno dopo.
  r.titolo('ferragosto.html — telefono 412px');
  ({ ctx, page } = await apri(browser, 'ferragosto.html', 412));

  // 1) L'anno non sta nell'indirizzo. Se qualcuno ci mettesse /ferragosto-2027
  //    la pagina ripartirebbe da zero proprio sulla query che si vince solo
  //    con l'anzianita' dell'URL.
  const canon = await page.$eval('link[rel=canonical]', (l) => l.getAttribute('href'));
  r.ok(/\/ferragosto\.html$/.test(canon), `canonical senza anno: ${canon}`);
  r.ok(!/\d{4}/.test(new URL(canon).pathname), 'nessun anno nel percorso');
  // L'anno pero' DEVE stare nel titolo, se no la pagina non dice di quale
  // Ferragosto parla.
  r.ok(/\b20\d{2}\b/.test(await page.title()), 'l\'anno sta nel <title>');

  // 2) Non e' un filtro di date. Quando il 15 cade di sabato o domenica
  //    l'elenco coincide con /eventi/weekend.html: quello che tiene le due
  //    pagine distinte e' il blocco su come ci si regola e dove si mangia,
  //    che manda a /luoghi.html. Toglierlo la trasforma in un doppione.
  r.ok(await page.locator('.ev-wrap p a[href="/luoghi.html"]').count() > 0,
    'il corpo manda a /luoghi.html (e non solo la nav)');

  const totF = await page.locator('.ev-wrap li[data-category]').count();
  const giorni = await page.locator('.ev-wrap .com-grp').count();
  if (totF) {
    r.ok(giorni > 0 && giorni <= 3, `il ponte sta in ${giorni} giorni (max 14-16)`);
    r.ok((await page.locator('.com-per').allTextContents()).some((t) => /Ferragosto/i.test(t)),
      'il 15 e\' etichettato "Ferragosto"');
    r.ok((await page.$eval('meta[name=robots]', (m) => m.content)).startsWith('index'),
      `con ${totF} eventi la pagina e' indicizzata`);
  } else {
    // Fuori stagione resta online - i link girati devono funzionare - ma
    // esce dall'indice invece di restare una pagina vuota indicizzata.
    r.ok((await page.$eval('meta[name=robots]', (m) => m.content)).startsWith('noindex'),
      'a vuoto la pagina e\' in noindex, follow');
  }
  await ctx.close();

  // ── halloween ─────────────────────────────────────────────────────────
  // Seconda pagina stagionale. Le prove sono quelle di ferragosto.html - un
  // URL che invecchia, e il blocco che la tiene distinta da un filtro di date
  // - piu' quella che vale solo qui: la pagina non deve mai dire da sola
  // quali eventi fanno paura.
  r.titolo('halloween.html — telefono 412px');
  ({ ctx, page } = await apri(browser, 'halloween.html', 412));

  const canonH = await page.$eval('link[rel=canonical]', (l) => l.getAttribute('href'));
  r.ok(/\/halloween\.html$/.test(canonH), `canonical senza anno: ${canonH}`);
  r.ok(!/\d/.test(new URL(canonH).pathname), 'nessuna cifra nel percorso');
  r.ok(/\b20\d{2}\b/.test(await page.title()), 'l\'anno sta nel <title>');

  // Il pezzo che un elenco di date non ha: la domanda "fa paura o no?" e il
  // rimando a /luoghi.html per il dove. Toglierli la rende un doppione di
  // /eventi/weekend.html, e a perdere sarebbe lei.
  r.ok((await page.locator('.ev-wrap h2').allTextContents())
    .some((t) => /fa paura/i.test(t)), 'il blocco "fa paura o no?" c\'è');
  r.ok(await page.locator('.ev-wrap p a[href="/luoghi.html"]').count() > 0,
    'il corpo manda a /luoghi.html (e non solo la nav)');

  const totH = await page.locator('.ev-wrap li[data-category]').count();
  const robotsH = await page.$eval('meta[name=robots]', (m) => m.content);
  if (totH) {
    // Le sezioni sono giorni della finestra 25/10-2/11: mai altri mesi.
    const mesi = (await page.locator('.ev-wrap .com-grp h3').allTextContents())
      .filter((t) => /\d/.test(t));
    r.ok(mesi.every((t) => /ottobre|novembre/i.test(t)),
      `la finestra resta 25 ottobre-2 novembre: ${mesi.join(' / ')}`);
  } else {
    r.ok(robotsH.startsWith('noindex'),
      'a vuoto la pagina è in noindex, follow: resta online ma fuori indice');
  }

  // La cernita che NON si fa: l'evidenza è "pensati per i più piccoli",
  // ricavata da e_per_bambini(). Una sezione che dichiari quali fanno paura
  // sarebbe un giudizio nostro su una festa altrui, dedotto dal titolo.
  const titoli = await page.locator('.ev-wrap .com-grp h3').allTextContents();
  r.ok(!titoli.some((t) => /paura|horror|brivid|spavent/i.test(t)),
    'nessuna sezione etichetta gli eventi come spaventosi');
  await ctx.close();

  // ── le sei pagine d'incrocio ──────────────────────────────────────────
  // Provincia X finestra temporale. Le prove qui difendono le tre cose per
  // cui esistono: la provincia nell'H1 (non solo nel title, che e' il difetto
  // di oggi.html/weekend.html), l'indirizzo senza data, e il fatto che dentro
  // ci sia davvero solo quella provincia - se no la pagina promette una cosa
  // e ne mostra un'altra.
  for (const [modo, prov, sigla] of [['oggi', 'alessandria', 'al'],
                                     ['weekend', 'asti', 'at'],
                                     ['oggi', 'cuneo', 'cn']]) {
    const file = `eventi/${modo}-provincia-${prov}.html`;
    r.titolo(`${file} — telefono 412px`);
    ({ ctx, page } = await apri(browser, file, 412));

    const h1 = (await page.textContent('h1')).trim();
    r.ok(new RegExp(`provincia di ${prov}`, 'i').test(h1),
      `la provincia sta nell'H1, non solo nel title: "${h1}"`);
    r.ok(/oggi|weekend/i.test(h1), 'e con lei la finestra temporale');

    // Stessa regola di /ferragosto.html: l'anno - e qualsiasi data - fuori
    // dall'indirizzo, se no la pagina riparte da zero a ogni stagione.
    const c = await page.$eval('link[rel=canonical]', (l) => l.getAttribute('href'));
    r.ok(!/\d/.test(new URL(c).pathname), `nessuna cifra nel percorso: ${c}`);

    const righe = await page.locator('.ev-wrap li[data-category]').count();
    if (righe) {
      r.ok(await page.evaluate((p) =>
        [...document.querySelectorAll('.ev-wrap li[data-province]')]
          .every((l) => l.dataset.province === p), sigla),
        `tutte le ${righe} righe sono della provincia ${sigla.toUpperCase()}`);
    }
    if (await page.locator('#lan-toolbar').count()) {
      r.ok(await page.locator('#lan-dove').count() === 0,
        'niente tendina provincia: la pagina E\' una provincia');
    }

    // Il robots si decide sulla finestra larga, non sugli eventi di oggi: e'
    // quello che evita a "oggi in provincia di Cuneo" di entrare e uscire
    // dall'indice ogni notte. Quello che si puo' controllare dal DOM e' il
    // patto che ne discende: indicizzata solo se ha qualcosa da mostrare.
    const robots = await page.$eval('meta[name=robots]', (m) => m.content);
    if (robots.startsWith('index')) {
      r.ok(righe > 0, `indicizzata e non vuota (${righe} righe)`);
    } else {
      r.ok(robots.startsWith('noindex'), 'fuori stagione: noindex, follow');
    }

    // Le briciole hanno il gradino in piu': queste pagine stanno SOTTO
    // /eventi/oggi.html, non accanto.
    r.ok(await page.locator(`.ev-crumb a[href="/eventi/${modo}.html"]`).count() > 0,
      'le briciole passano dalla pagina madre');

    // L'anello fra le tre sorelle, e nessun link a se stessa.
    const altre = await page.$$eval('.com-link a[href*="-provincia-"]',
      (a) => a.map((x) => x.getAttribute('href')));
    r.ok(altre.length >= 2, `rimanda alle altre province (${altre.length})`);
    r.ok(!altre.some((h) => h.endsWith(`${modo}-provincia-${prov}.html`)),
      'e non a se stessa');
    await ctx.close();
  }

  // Le due pagine trasversali fanno da indice: se questo blocco sparisce, le
  // sei nascono orfane e non le trova nessuno.
  for (const modo of ['oggi', 'weekend']) {
    r.titolo(`eventi/${modo}.html — indice delle provinciali`);
    ({ ctx, page } = await apri(browser, `eventi/${modo}.html`, 412));
    const giu = await page.$$eval('.com-link a[href*="-provincia-"]',
      (a) => a.map((x) => x.getAttribute('href')));
    r.ok(giu.length === 3, `linka tutte e tre le provinciali (${giu.length})`);
    r.ok(giu.every((h) => h.includes(`${modo}-provincia-`)),
      'e sono quelle della sua finestra temporale');
    // Meta' della query e' il posto: prima le province stavano solo nel title.
    r.ok(/provincia di/i.test(await page.textContent('h1')),
      'l\'H1 nomina le province');
    await ctx.close();
  }

  // ── "Vicino a me" sulle pagine di intenzione ──────────────────────────
  // E' lo stesso modulo dell'agenda (/assets/js/daop-vicino.js) su un DOM
  // diverso: righe <li> nascoste con `hidden` invece di schede con una classe.
  // Qui si prova proprio l'innesto, cioe' che il modulo si sommi ai filtri di
  // questa pagina invece di ignorarli.
  for (const pag of ['eventi/oggi.html', 'sagre-provincia-alessandria.html']) {
    r.titolo(`${pag} — vicino a me`);
    ({ ctx, page } = await apri(browser, pag, 412, () => {
      window.__geo = 0;
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition = function () { window.__geo++; };
      }
    }));

    const righe = await page.locator('.ev-wrap li[data-category]').count();
    const conCoord = await page.locator('.ev-wrap li[data-lat][data-lon]').count();
    if (!(await page.locator('#ev-geo').count())) {
      r.ok(conCoord < 12, `niente controllo con ${conCoord} righe georiferite (sotto la soglia)`);
      await ctx.close();
      continue;
    }

    r.ok(await page.evaluate(() => window.__geo) === 0,
      'la posizione NON si chiede al caricamento');
    // Stessa soglia dell'agenda, per la stessa ragione: le due colonne del
    // foglio si compilano a mano, e una riga scoperta resta fuori dal raggio
    // per scelta. Quello che deve restare rosso e' il crollo, non la cella
    // vuota. Vedi il commento lungo in tests/agenda.js.
    const COPERTURA_MIN = 0.95;
    r.ok(conCoord >= Math.ceil(righe * COPERTURA_MIN),
      `le righe portano le coordinate: ${conCoord}/${righe}`
      + ` (soglia ${Math.ceil(righe * COPERTURA_MIN)})`);
    if (conCoord < righe) {
      console.log(`  --   ${righe - conCoord} righe senza coordinate `
        + '(Lat/Lng da riempire nel foglio, non un difetto del generatore)');
    }
    r.ok(await page.locator('#ev-geo').isVisible(),
      'il modulo condiviso si e\' acceso anche qui');

    await page.locator('#ev-geo-alt').click();
    await page.waitForTimeout(200);
    const comune = await page.locator('#ev-geo-list option').first().getAttribute('value');
    await page.fill('#ev-geo-q', comune);
    await page.waitForTimeout(350);

    const raggio = parseInt(await page.locator('#ev-geo-chips button[aria-pressed="true"]')
      .textContent(), 10);
    const dopo = await visibili(page);
    r.ok(dopo > 0 && dopo < righe,
      `il raggio (${raggio} km da ${comune}) restringe: ${dopo}/${righe}`);
    r.ok(await page.evaluate(() => {
      const male = [];
      document.querySelectorAll('.ev-wrap li[data-category]:not([hidden])').forEach((l) => {
        const t = l.querySelector('.ev-km');
        if (!t) return male.push(1);
        return null;
      });
      return male.length === 0;
    }), 'ogni riga rimasta dichiara la sua distanza');

    // Il conteggio della pagina deve accorgersi del raggio: prima contava solo
    // ricerca e tendine, e con il solo raggio attivo sarebbe restato muto.
    r.ok(/\d+ eventi? con questi filtri/.test(await page.textContent('#lan-count')),
      'il conteggio della pagina considera anche il raggio');

    // I gradini contano dentro gli altri filtri, non sul totale della pagina.
    if (await page.locator('#lan-tipo').count()) {
      const primaDelTipo = await page.locator('#ev-geo-chips button').last().textContent();
      const cat = await page.$eval('#lan-tipo', (s) => s.options[1].value);
      await page.selectOption('#lan-tipo', cat);
      await page.waitForTimeout(300);
      const dopoIlTipo = await page.locator('#ev-geo-chips button').last().textContent();
      r.ok(primaDelTipo !== dopoIlTipo,
        `i gradini contano dentro gli altri filtri (${primaDelTipo.trim()} -> ${dopoIlTipo.trim()})`);
      await page.selectOption('#lan-tipo', 'all');
      await page.waitForTimeout(200);
    }

    await page.locator('#ev-geo-clear').click();
    await page.waitForTimeout(300);
    r.ok(await visibili(page) === righe, 'la ✕ rimette tutte le righe');
    r.ok(await page.locator('.ev-km').count() === 0, 'la ✕ toglie le distanze');
    await ctx.close();
  }

  return r;
};
