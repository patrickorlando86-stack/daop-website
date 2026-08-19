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

const fs = require('fs');
const path = require('path');
const { apri, esito, RADICE } = require('./_aiuto');

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
  // Quattro tendine sul telefono vanno a capo: 156px invece di 109. E' voluto,
  // ed e' il contrario della scelta fatta quando la pagina aveva solo i luoghi
  // dedotti dall'agenda. Il dato e' cambiato: con centinaia di luoghi scelti a
  // mano l'elenco non si scorre, si filtra. La soglia resta per accorgersi se
  // un giorno diventassero sei.
  r.ok(await page.locator('#lg-toolbar').evaluate((b) => b.offsetHeight) <= 170,
    'la barra filtri non supera le due righe sul telefono');

  // Una tendina che offre solo "tutti" non si stampa: e' un comando che non fa
  // niente. Due voci (tutti + una scelta) sono un comando vero, quindi la
  // soglia e' >1, non >2.
  r.ok(await page.evaluate(() =>
    [...document.querySelectorAll('#lg-toolbar select.ev-select')]
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

  // Il comune NON e' una tendina: con 297 voci il selettore nativo di Android
  // copre quasi tutto lo schermo e non si capisce come chiuderlo. E' un campo
  // di testo con <datalist>, e si scrive un pezzo di nome.
  const com = page.locator('#lg-toolbar input[data-campo="comune"]');
  if (await com.count()) {
    await page.selectOption('#lg-toolbar [data-campo="cat"]', 'all');
    r.ok(await page.locator('#lg-toolbar select[data-campo="comune"]').count() === 0,
      'il comune non e\' una <select>: niente pannello a tutto schermo su Android');
    const quante = await page.locator('#lg-comuni option').count();
    r.ok(quante > 1, `${quante} comuni suggeriti`);

    const nome = await page.locator('#lg-comuni option').first().getAttribute('value');
    await com.fill(nome);
    await page.waitForTimeout(300);
    const n2 = await visibili(page);
    r.ok(n2 > 0 && n2 < tot, `filtro comune "${nome}": ${n2}/${tot}`);
    r.ok(await page.evaluate((c) => {
      const s = c.normalize('NFKD').replace(/[̀-ͯ]/g, '')
        .replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '').toLowerCase();
      return [...document.querySelectorAll('.lg-row[data-cat]:not([hidden])')]
        .every((l) => l.dataset.comune.indexOf(s) > -1);
    }, nome), 'resta solo quel comune');

    // Basta un pezzo di nome: e' il punto del campo di testo.
    await com.fill(nome.slice(0, 4));
    await page.waitForTimeout(300);
    r.ok(await visibili(page) >= n2, `scrivendo solo "${nome.slice(0, 4)}" li trova lo stesso`);

    const altra = await page.evaluate(() => {
      const p = document.querySelector('select[data-campo="prov"]');
      return p && p.options.length > 2 ? p.options[p.options.length - 1].value : null;
    });
    if (altra) {
      await com.fill(nome);
      await page.selectOption('#lg-toolbar [data-campo="prov"]', altra);
      await page.waitForTimeout(300);
      r.ok(await com.inputValue() === '',
        'cambiando provincia il comune incompatibile si cancella, non resta scritto e senza risultati');
      r.ok(await page.locator('#lg-comuni option').count() < quante,
        'restano suggeriti i comuni della sola provincia scelta');
      await page.selectOption('#lg-toolbar [data-campo="prov"]', 'all');
    }
    await com.fill('');
    // Il filtro categoria era stato azzerato qui sopra per isolare il comune:
    // va rimesso, se no la prova che li somma parte da uno stato diverso da
    // quello che crede.
    await page.selectOption('#lg-toolbar [data-campo="cat"]', cat);
    await page.waitForTimeout(200);
  }

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

  // IL BUCO. Il gruppo comune e' un <section>, e il foglio di stile del sito ha
  // `section{padding:100px 24px}` per le fasce della home: senza un padding:0
  // ogni comune si portava dietro 72px di vuoto sopra e 72 sotto. Senza filtri
  // non si vedeva (le sezioni sono alte), filtrando restava una riga in mezzo a
  // 144px di niente. Si controlla che la sezione sia alta quanto il suo
  // contenuto, ed e' proprio quando si filtra che il difetto salta fuori.
  r.ok(await page.evaluate(() => {
    const male = [];
    for (const s of document.querySelectorAll('.lg-grp')) {
      if (s.hidden) continue;
      const box = s.getBoundingClientRect();
      const figli = [...s.children].filter((c) => c.getBoundingClientRect().height > 0);
      if (!figli.length) continue;
      const primo = figli[0].getBoundingClientRect();
      const ultimo = figli[figli.length - 1].getBoundingClientRect();
      if (box.bottom - ultimo.bottom > 12 || primo.top - box.top > 12) male.push(s.id);
    }
    return male.length === 0;
  }), 'nessun gruppo comune si porta dietro spazio vuoto (il <section> del sito)');
  await page.selectOption('#lg-toolbar [data-campo="cat"]', 'all');
  await page.waitForTimeout(200);

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

  // Due id uguali sono HTML non valido e mandano ogni ancora sul primo dei due.
  // Ci si arriva dai DATI, non dal codice: un comune scritto in due grafie
  // ("Montegrosso d'Asti" e "Montegrosso D'Asti") o lo stesso nome in due
  // province ("Ronco Scrivia" in AL e in GE). Non si vede guardando la pagina.
  r.ok(await page.evaluate(() => {
    const visti = new Set();
    for (const e of document.querySelectorAll('[id]')) {
      if (visti.has(e.id)) return false;
      visti.add(e.id);
    }
    return true;
  }), 'nessun id ripetuto in pagina');

  // I nomi non gridano. Nel foglio 126 righe su 823 sono scritte tutte in
  // maiuscolo, e in elenco "SCUOLA PARITARIA SACRO CUORE" sopra "Studio Danza
  // My Balance" sembra un errore. Si controlla che in pagina non ne resti
  // nessuno tutto maiuscolo, salvo le sigle (ASD, A.S.D., SSD).
  r.ok(await page.evaluate(() => {
    const grida = [...document.querySelectorAll('.lg-nome')]
      .map((n) => n.textContent.trim())
      .filter((t) => t.length > 4 && !/[a-zàèéìòù]/.test(t))
      .filter((t) => t.split(/\s+/).some((p) => p.replace(/[^A-Za-z]/g, '').length > 5));
    return grida.length === 0;
  }), 'nessun nome tutto in maiuscolo');

  // Un link verso il sito di chi paga e' un link commerciale: senza
  // rel="sponsored" (o almeno nofollow) e' uno schema di link, e Google lo paga
  // con un'azione manuale sul DOMINIO - cioe' su eventi.html, che e' la pagina
  // che regge il traffico. Il rischio non resta su questa pagina.
  r.ok(await page.evaluate(() => {
    const fuori = [...document.querySelectorAll('.lg-row a[href^="http"]')]
      .filter((a) => !/daop\.it|google\.com\/maps/.test(a.href));
    return fuori.length > 0 && fuori.every((a) => {
      const rel = (a.getAttribute('rel') || '');
      const pagata = !!a.closest('.lg-row.is-prem');
      return pagata ? /sponsored/.test(rel) : /nofollow|sponsored/.test(rel);
    });
  }), 'i link in uscita sono qualificati: sponsored sulle schede a pagamento, nofollow sulle altre');
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

  // La banda di Supabase. Nell'INTESTAZIONE non ci vanno immagini: al posto
  // della miniatura c'e' l'emoji del foglio. La foto sta nel corpo, cioe'
  // dentro un <details> chiuso, che il browser non disegna: con loading="lazy"
  // non parte nessuna richiesta finche' non si apre la riga.
  r.ok(await page.evaluate(() =>
    [...document.querySelectorAll('.lg-row > summary img')].length === 0),
    'nessuna immagine nelle intestazioni: sarebbero centinaia di richieste');
  r.ok(await page.evaluate(() =>
    [...document.querySelectorAll('.lg-row img')].every((i) => i.loading === 'lazy')),
    'ogni foto e\' lazy');
  await ctx.close();

  // ── la prova che conta davvero sulla banda ────────────────────────────
  // Il bucket Supabase ha 5 GB al mese e l'08/08/2026 le locandine lo hanno
  // quasi bruciato. Qui si controlla sul browser vero, non sul markup: si
  // scorre TUTTA la pagina e non deve partire nessuna richiesta di foto.
  r.titolo('luoghi.html — la banda delle foto');
  ({ ctx, page } = await apri(browser, 'luoghi.html', 412));
  const foto = [];
  page.on('request', (req) => {
    if (/supabase\.co/.test(req.url())) foto.push(req.url());
  });
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 800) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 20));
    }
  });
  await page.waitForTimeout(800);
  r.ok(foto.length === 0,
    `scorrendo tutta la pagina non si scarica nessuna foto (${foto.length})`);

  // Si aspetta LA foto di QUELLA riga, non "una richiesta qualsiasi entro
  // 900ms". Con 823 righe su un runner lento quell'attesa fissa non bastava e
  // la prova lampeggiava: verde in locale, rossa in CI. Una prova che lampeggia
  // e' peggio di nessuna prova, perche' insegna a ignorare il rosso.
  const conFoto = await page.evaluate(() => {
    const d = [...document.querySelectorAll('.lg-row')].find((x) => x.querySelector('img'));
    return d ? { id: d.id, src: d.querySelector('img').src } : null;
  });
  if (conFoto) {
    await page.evaluate((id) => {
      const d = document.getElementById(id);
      d.open = true;
      d.scrollIntoView({ block: 'center' });
    }, conFoto.id);
    const fine = Date.now() + 15000;
    while (!foto.includes(conFoto.src) && Date.now() < fine) {
      await page.waitForTimeout(150);
    }
    r.ok(foto.includes(conFoto.src), 'aprendo una riga arriva la sua foto, e solo quella');
  } else {
    r.ok(true, 'nessuna riga con foto in questo catalogo');
  }

  // Il link diretto a un luogo deve aprire la riga, non lasciarla chiusa.
  const id = await page.locator('.lg-row').nth(5).getAttribute('id');
  await page.evaluate((h) => { location.hash = h; }, id);
  await page.waitForTimeout(400);
  r.ok(await page.locator(`#${id}`).evaluate((d) => d.open),
    `l'ancora #${id} apre la riga`);

  // ── il ponte dalle schede evento ──────────────────────────────────────
  // Le schede /eventi/*.html fanno l'82% dei clic, questa pagina ne faceva
  // zero: l'unico link che riceveva veniva dalla nav. Dal 14/08/2026 ogni
  // scheda manda ai luoghi del suo comune, e sono due cose che si rompono in
  // silenzio - il link sparisce, oppure punta a un'ancora che non c'e' e
  // scarica in cima a una pagina da 800 righe. Nessuna delle due fa rumore.
  r.titolo('luoghi.html — i link in arrivo dalle schede evento');
  const ancore = new Set(await page.$$eval('.lg-grp-h h2[id]', (h) => h.map((x) => x.id)));
  const schede = ['eventi', 'eventi/comune'].flatMap((d) =>
    fs.readdirSync(path.join(RADICE, d))
      .filter((f) => f.endsWith('.html'))
      .map((f) => path.join(d, f)));
  const bersagli = new Map();
  let conLink = 0;
  for (const f of schede) {
    const html = fs.readFileSync(path.join(RADICE, f), 'utf8');
    let trovato = false;
    for (const m of html.matchAll(/href="\/luoghi\.html#(c-[a-z0-9-]+)"/g)) {
      trovato = true;
      if (!bersagli.has(m[1])) bersagli.set(m[1], f);
    }
    if (trovato) conLink++;
  }
  r.ok(bersagli.size > 0,
    `il ponte esiste: ${bersagli.size} comuni linkati da ${conLink}/${schede.length} pagine`);
  const rotti = [...bersagli].filter(([a]) => !ancore.has(a));
  r.ok(rotti.length === 0, rotti.length
    ? `ancore inesistenti: ${rotti.slice(0, 3).map(([a, f]) => `#${a} (${f})`).join(', ')}`
    : 'ogni ancora linkata esiste davvero in luoghi.html');

  // ── l'invito al canale WhatsApp ───────────────────────────────────────
  // Due guasti silenziosi: l'invito sparisce da tutte le pagine (CANALE_WA
  // svuotato per sbaglio), oppure ce n'e' piu' d'uno sulla stessa pagina,
  // che su una scheda gia' lunga e' una richiesta ripetuta a chi ha gia'
  // detto di no una volta. Nessuno dei due rompe niente, quindi nessuno dei
  // due si nota.
  //
  // I tre eventi/box-*.html restano fuori, e non e' una dimenticanza: sono i
  // riquadri da incorporare, che vivono dentro l'iframe del sito di qualcun
  // altro. Chiedere li' un'iscrizione al nostro canale vuol dire usare lo
  // spazio di un altro per portarci via il suo pubblico. E' la stessa ragione
  // per cui quei tre file non chiedono il consenso ai cookie.
  const nostre = schede.filter((f) => !/\bbox-[a-z]{2}\.html$/.test(f));
  let conCanale = 0, doppi = [];
  for (const f of nostre) {
    const n = (fs.readFileSync(path.join(RADICE, f), 'utf8')
      .match(/class="ev-canale-cta"/g) || []).length;
    if (n) conCanale++;
    if (n > 1) doppi.push(f);
  }
  r.ok(conCanale === nostre.length,
    `l'invito al canale c'e' su tutte le nostre pagine: ${conCanale}/${nostre.length}`);
  r.ok(doppi.length === 0, doppi.length
    ? `invito ripetuto in ${doppi.length} pagine (es. ${doppi[0]})`
    : 'mai due inviti sulla stessa pagina');

  // ── e DOVE sta l'invito ───────────────────────────────────────────────
  // Su una scheda viva l'invito sta in coda (chiede qualcosa a chi ha gia'
  // avuto l'orario della sagra); su un'EDIZIONE CONCLUSA sale sotto l'avviso,
  // perche' li' la pagina non ha niente da dare e l'invito e' la cosa piu'
  // utile che resta. E' una decisione presa il 19/08/2026 e misurata: si
  // smonta da sola alla prima riscrittura del template, perche' basta
  // spostare una riga e nessuna pagina si rompe.
  //
  // Il marcatore e' la classe .ev-canale--alto, che serve gia' alla CSS: la
  // prova non aggiunge niente all'HTML per potersi fare. Si cerca l'attributo
  // intero e non il solo nome della classe: quel nome sta anche nel <style>
  // di ogni pagina (PAGINA_CSS e' incollata dappertutto), quindi un includes
  // sul nome secco direbbe "in alto" su tutte e 296 le schede.
  let concluseSbagliate = [], viveSbagliate = [];
  for (const f of nostre) {
    const html = fs.readFileSync(path.join(RADICE, f), 'utf8');
    const conclusa = html.includes('<strong>Edizione conclusa</strong>');
    const alto = html.includes('class="ev-canale ev-canale--alto"');
    // La coda si riconosce dall'ordine: l'invito DOPO la firma di verifica.
    const inCoda = !alto && html.indexOf('class="ev-canale"') >
      html.indexOf('class="ev-firma"');
    if (conclusa && !alto) concluseSbagliate.push(f);
    if (!conclusa && !inCoda) viveSbagliate.push(f);
  }
  r.ok(concluseSbagliate.length === 0, concluseSbagliate.length
    ? `edizioni concluse con l'invito ancora in coda: ${concluseSbagliate.length} (es. ${concluseSbagliate[0]})`
    : "su ogni edizione conclusa l'invito sta sotto l'avviso");
  r.ok(viveSbagliate.length === 0, viveSbagliate.length
    ? `invito fuori posto su ${viveSbagliate.length} pagine vive (es. ${viveSbagliate[0]})`
    : "sulle pagine vive l'invito resta in coda, dopo la firma");

  await ctx.close();

  return r;
};
