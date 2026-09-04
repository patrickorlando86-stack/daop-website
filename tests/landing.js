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
async function provaNonSoloSagre(r, page, prov) {
  const righe = await page.locator('.ev-wrap li[data-category]').count();
  const nonSagre = await page.locator('.ev-wrap li[data-category]:not([data-category=feste])')
    .count();

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
  const attraverso = await page.evaluate(() => {
    const m = new Map();
    document.querySelectorAll('.ev-wrap li[data-category]').forEach((l) => {
      const a = l.querySelector('a.com-go');
      if (!a) return;
      const h = a.getAttribute('href');
      (m.get(h) || m.set(h, new Set()).get(h)).add(l.dataset.category === 'feste');
    });
    return [...m].filter(([, s]) => s.size > 1).map(([h]) => h);
  });
  r.ok(attraverso.length === 0,
    `${prov}: nessuna scheda compare sopra e sotto insieme (${righe} righe)`
    + (attraverso.length ? ': ' + attraverso.slice(0, 3).join(', ') : ''));

  // 2-bis) Il ponte verso la sorella senza finestra temporale. Non e'
  //    cortesia: /eventi-provincia-<x>.html nasce con zero link entranti, e
  //    "alla nav non ci va nessuno" (lezione del 14/08 su luoghi.html). Se
  //    questo link sparisce, la pagina nuova torna orfana.
  r.ok(await page.locator('.ev-wrap a[href^="/eventi-provincia-"]').count() > 0,
    `${prov}: manda alla sorella senza finestra temporale`);

  // 3) LA REGRESSIONE VERA. La tendina delle categorie si costruisce
  //    dall'elenco che _landing_filtri riceve: passandogli le sole sagre
  //    resterebbe con una voce sola, e una tendina da una voce non si stampa
  //    affatto - cioe' il filtro sparirebbe con settanta righe in pagina e
  //    cinque categorie da separare. Non si legge nell'HTML: si vede solo
  //    confrontando le opzioni con le righe.
  if (righe >= 12) {
    const mancanti = await page.evaluate(() => {
      const sel = document.getElementById('lan-tipo');
      if (!sel) return ['(la tendina delle categorie non viene stampata)'];
      const opz = new Set([...sel.options].map((o) => o.value));
      const cat = new Set([...document.querySelectorAll('.ev-wrap li[data-category]')]
        .map((l) => l.dataset.category));
      return [...cat].filter((c) => !opz.has(c));
    });
    r.ok(mancanti.length === 0,
      `${prov}: la tendina conosce tutte le categorie in pagina${mancanti.length ? ': manca ' + mancanti.join(', ') : ''}`);
  }

  // 4) Le sagre restano il contenuto principale: il blocco in coda sta DOPO
  //    l'ultima riga del calendario, se no la pagina si apre su quello che
  //    non e' la sua query.
  r.ok(await page.evaluate(() => {
    const li = [...document.querySelectorAll('.ev-wrap li[data-category]')];
    const ultimaSagra = li.map((l, i) => [l.dataset.category, i])
      .filter(([c]) => c === 'feste').pop();
    const primaAltra = li.findIndex((l) => l.dataset.category !== 'feste');
    return !ultimaSagra || primaAltra === -1 || primaAltra > ultimaSagra[1];
  }), `${prov}: le ${righe - nonSagre} sagre stanno prima delle ${nonSagre} altre`);

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

// Le /eventi-provincia-*.html: la provincia SENZA finestra temporale, divisa
// per eta'. Vedi spec_eventi_prov() in genera_eventi.py per il perche' esiste
// dopo che spec_sagre diceva di non farla.
//
// Nessuna di queste prove asserisce un CONTEGGIO, ed e' deliberato: "48
// pensati per i bambini" e' rosso la prima notte che una locandina arriva
// senza la cella dell'eta' compilata, cioe' quando il sito fa la cosa giusta.
// E' l'inciampo gia' pagato sei volte in questo repo - la copertura delle
// coordinate, il conteggio delle quattro porte, il robots delle pagine
// realta'. Qui si controllano rapporti fra insiemi, che non hanno una taglia
// giusta.
async function provaEventiProv(r, page, prov, slug) {
  const righe = await page.locator('.ev-wrap li[data-category]').count();

  // 1) IDENTITA'. La query e' "eventi e attivita' per bambini in provincia di
  //    X" e sta per intero nel title e nell'H1 - su Alessandria il "| DAOP"
  //    cade da solo perche' _landing_titolo() taglia a 62 caratteri, e va
  //    bene: quello che non puo' cadere e' la frase.
  const atteso = new RegExp(`^Eventi e attività per bambini in provincia di ${prov}`);
  r.ok(atteso.test(await page.$eval('h1', (h) => h.textContent.trim())),
    `${prov}: l'H1 e' la query per intero`);
  r.ok(atteso.test(await page.title()), `${prov}: e anche il <title>`);
  r.ok(new RegExp(`/eventi-provincia-${slug}\\.html$`)
    .test(await page.$eval('link[rel=canonical]', (l) => l.getAttribute('href'))),
    `${prov}: canonical proprio`);
  // La guardia contro la fusione con la sorella: il giorno che qualcuno
  // decide di "unificare le due pagine provinciali", una delle due perde la
  // sua query. Questa non e' una pagina di sagre e non deve dirlo.
  r.ok(!/sagre/i.test(await page.title()), `${prov}: "sagre" non entra nel title`);

  // 2) E' L'AGENDA INTERA, non un sottoinsieme. Se un giorno qualcuno la
  //    filtrasse (per categoria, per eta', per "solo i prossimi 30 giorni")
  //    diventerebbe il doppione di una delle altre tre provinciali.
  const cats = await page.evaluate(() => [...new Set([...document
    .querySelectorAll('.ev-wrap li[data-category]')].map((l) => l.dataset.category))]);
  r.ok(cats.length > 1,
    `${prov}: in pagina ci sono ${cats.length} categorie, non una (${cats.join(', ')})`);
  r.ok(await page.evaluate(() => [...document.querySelectorAll('.ev-wrap li[data-province]')]
    .every((l, _i, a) => l.dataset.province === a[0].dataset.province)),
    `${prov}: tutte le righe sono della stessa provincia`);

  // 3) I DUE BLOCCHI PARTIZIONANO LE RIGHE. Non "ogni href compare una volta
  //    sola": una manifestazione di piu' giorni ha piu' righe che puntano
  //    alla stessa scheda, ed e' giusto - lo fa il calendario delle sagre da
  //    sempre, e una prova che lo vietasse sarebbe nata rossa (e' successo,
  //    il 29/08, sulla sezione "Non solo sagre"). Quello che deve valere e'
  //    che ogni RIGA stia in un blocco e uno solo: se i due elenchi
  //    smettessero di essere complementari la pagina direbbe due volte la
  //    stessa cosa sotto due titoli che si contraddicono.
  const blocchi = await page.evaluate(() =>
    [...document.querySelectorAll('.ev-wrap .com-grp')]
      .filter((g) => g.querySelector('li[data-category]'))
      .map((g) => ({
        titolo: (g.querySelector('h3') || {}).textContent || '',
        righe: g.querySelectorAll('li[data-category]').length,
      })));
  const somma = blocchi.reduce((a, b) => a + b.righe, 0);
  r.ok(somma === righe,
    `${prov}: ogni riga sta in un blocco solo (${somma} di ${righe} in ${blocchi.length} blocchi)`);

  // 4) IL BLOCCO DEI BAMBINI VIENE PRIMO. E' la risposta alla query: se
  //    finisse sotto, la pagina si aprirebbe su "gli altri appuntamenti",
  //    cioe' sulla meta' che quella domanda non l'ha fatta. Stessa aritmetica
  //    per cui su sagre-provincia-* le sagre stanno prima del resto.
  if (blocchi.length > 1) {
    r.ok(/pensati per i bambini/i.test(blocchi[0].titolo),
      `${prov}: il primo blocco e' "${blocchi[0].titolo.trim()}"`);
  } else {
    // Una provincia dove tutto ha (o niente ha) la fascia d'eta' ha un blocco
    // solo: non e' un guasto.
    r.ok(true, `${prov}: un blocco solo, niente ordine da controllare`);
  }

  // 5) L'ETA' SI VEDE IN RIGA. E' il difetto che la pagina ha avuto nascendo:
  //    la sezione si intitola "Pensati per i bambini" e promette la fascia
  //    dichiarata, ma _landing_righe() stampava quando, categoria, nome e
  //    comune - non l'eta'. La pagina che vive di quel dato era l'unica a non
  //    mostrarlo, ed e' la forma dell'occhiello dei corsi che prometteva i
  //    costi che il foglio non ha.
  const pillole = await page.locator('.ev-wrap .com-eta').count();
  if (/pensati per i bambini/i.test((blocchi[0] || {}).titolo || '')) {
    r.ok(pillole > 0, `${prov}: la fascia d'età si legge in riga (${pillole} pillole)`);
    r.ok(await page.evaluate(() => [...document.querySelectorAll('.ev-wrap .com-eta')]
      .every((s) => s.textContent.trim().length > 0)),
      `${prov}: nessuna pillola d'età vuota`);
  }

  // 6) E NON ROMPE LA RIGA. Questo non si vede nell'HTML: e' la classe di
  //    guasto della barra delle azioni che veniva alta 915px e della gola di
  //    62px dei programmi senza data - markup giusto, reso sbagliato. Una
  //    pillola in piu' dentro un contenitore flex puo' schiacciare il titolo
  //    in una colonna stretta, e allora la riga si legge male proprio dove
  //    l'evento e' per i bambini.
  if (pillole > 0) {
    const stretti = await page.evaluate(() =>
      [...document.querySelectorAll('.ev-wrap .com-eta')].map((s) => {
        const li = s.closest('li');
        const a = li && li.querySelector('a.com-go');
        if (!a) return 1;
        return a.getBoundingClientRect().width / li.getBoundingClientRect().width;
      }).filter((q) => q < 0.35).length);
    r.ok(stretti === 0,
      `${prov}: la pillola non schiaccia il titolo (${stretti} righe sotto il 35%)`);
    r.ok(await page.evaluate(() =>
      document.documentElement.scrollWidth <= window.innerWidth + 1),
      `${prov}: la pagina non scorre in orizzontale`);

    // E' UN CHIP, NON UNA FASCIA. La prima versione di questa prova non lo
    // chiedeva, ed e' passata verde mentre la pillola era larga 251px su 375
    // e si prendeva una riga tutta sua: .com-b e' un flex in COLONNA, quindi
    // un figlio in piu' occupa l'intera larghezza. .com-eta era nata per
    // .com-kids delle pagine comune, che e' un flex in riga. Il difetto si
    // vede solo misurando la pillola - non il titolo, non lo scroll.
    const fasce = await page.evaluate(() =>
      [...document.querySelectorAll('.ev-wrap .com-eta')].map((s) => {
        const li = s.closest('li');
        const b = s.getBoundingClientRect();
        return {
          quota: b.width / li.getBoundingClientRect().width,
          righe: b.height / parseFloat(getComputedStyle(s).lineHeight || 20),
          t: s.textContent.trim(),
        };
      }).filter((x) => x.quota > 0.7 || x.righe > 1.6));
    r.ok(fasce.length === 0,
      `${prov}: la fascia d'età sta in un chip di una riga`
      + (fasce.length ? `: ${fasce.length} larghe/alte, es. "${fasce[0].t}"` : ''));
  }

  // 7) LA TENDINA CONOSCE TUTTE LE CATEGORIE IN PAGINA. La stessa regressione
  //    delle sagre-provincia-*: _landing_filtri costruisce le opzioni
  //    dall'elenco che riceve, e passandogli un sottoinsieme (per esempio i
  //    soli 'bimbi') il filtro nasconderebbe righe senza avere la voce per
  //    farle tornare. Non si legge nell'HTML.
  if (righe >= 12) {
    const mancanti = await page.evaluate(() => {
      const sel = document.getElementById('lan-tipo');
      if (!sel) return ['(la tendina delle categorie non viene stampata)'];
      const opz = new Set([...sel.options].map((o) => o.value));
      return [...new Set([...document.querySelectorAll('.ev-wrap li[data-category]')]
        .map((l) => l.dataset.category))].filter((c) => !opz.has(c));
    });
    r.ok(mancanti.length === 0,
      `${prov}: la tendina conosce tutte le categorie${mancanti.length ? ': manca ' + mancanti.join(', ') : ''}`);
    r.ok(await page.locator('#lan-dove').count() === 0,
      `${prov}: niente tendina provincia, la pagina E' una provincia`);
  }

  // 8) IL FILTRO ATTRAVERSA I DUE BLOCCHI. Le categorie stanno in tutti e due
  //    (l'asse della pagina e' l'eta', non la categoria): filtrando su una
  //    categoria devono restare righe e i blocchi svuotati devono sparire col
  //    loro titolo, che qui sta DENTRO la sezione.
  if (await page.locator('#lan-tipo').count()) {
    const c = await page.$eval('#lan-tipo', (s) => s.options[1].value);
    await page.selectOption('#lan-tipo', c);
    await page.waitForTimeout(250);
    const n = await page.locator('.ev-wrap li[data-category]:not([hidden])').count();
    r.ok(n > 0 && n < righe, `${prov}: filtro "${c}" ${n}/${righe}`);
    r.ok(await page.evaluate(() => [...document.querySelectorAll('.ev-wrap .com-grp')]
      .filter((g) => g.querySelector('li[data-category]'))
      .every((g) => g.hidden === !g.querySelector('li[data-category]:not([hidden])'))),
      `${prov}: i blocchi rimasti vuoti spariscono`);
    await page.selectOption('#lan-tipo', 'all');
    await page.waitForTimeout(200);
  }

  // 9) IL FILTRO "QUANDO", che sulle altre pagine di intenzione NON c'e'
  //    apposta: quelle SONO una risposta a quando, e una seconda domanda sul
  //    tempo le contraddirebbe. Qui la premessa cade - questa pagina e'
  //    definita dal non avere una finestra temporale - quindi il filtro
  //    risponde alla domanda che l'elenco lascia aperta.
  // La presenza NON e' condizionale: su queste pagine il controllo c'e' per
  // costruzione. Dentro un `if (…count())` il difetto "tendina togliata dalla
  // barra" avrebbe saltato l'intero blocco senza far fallire niente - trovato
  // rimettendo il difetto, non ragionandoci.
  r.ok(await page.locator('#lan-quando').count() > 0,
    `${prov}: il filtro "quando" c'è`);
  if (await page.locator('#lan-quando').count()) {
    // Il dato su cui lavora, chiesto per primo. Senza questa riga il difetto
    // "le date sparite dalle righe" passerebbe verde: il filtro nasconderebbe
    // TUTTO, e zero righe sono coerenti con qualunque finestra. E' la stessa
    // forma della prova sulla copertura delle coordinate.
    const senzaDate = await page.evaluate(() =>
      [...document.querySelectorAll('.ev-wrap li[data-category]')]
        .filter((l) => !/^\d{4}-\d{2}-\d{2}$/.test(l.dataset.start || '')
                    || !/^\d{4}-\d{2}-\d{2}$/.test(l.dataset.end || '')).length);
    r.ok(senzaDate === 0,
      `${prov}: ogni riga dichiara le sue date${senzaDate ? `: ${senzaDate} senza` : ''}`);

    const esiti = {};
    for (const v of ['oggi', 'weekend', '7', 'mese']) {
      await page.selectOption('#lan-quando', v);
      await page.waitForTimeout(220);
      esiti[v] = await page.evaluate(() => {
        const viste = [...document.querySelectorAll('.ev-wrap li[data-category]:not([hidden])')];
        const iso = (d) => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0')
          + '-' + String(d.getDate()).padStart(2, '0');
        const o = new Date(); o.setHours(0, 0, 0, 0);
        return { n: viste.length, oggi: iso(o), righe: viste.map((l) => [l.dataset.start, l.dataset.end]) };
      });
    }
    // Coerenza: con "oggi" ogni riga rimasta deve DAVVERO essere in corso
    // oggi. Vale anche a zero righe, che in un martedi' di novembre e' la
    // risposta giusta - per questo la prova non pretende n>0.
    const sballate = esiti.oggi.righe.filter(([a, b]) => !(a <= esiti.oggi.oggi && b >= esiti.oggi.oggi));
    r.ok(sballate.length === 0,
      `${prov}: con "oggi" restano solo eventi in corso oggi (${esiti.oggi.n} righe)`);
    // E il controllo non e' arredamento: almeno una delle quattro opzioni
    // cambia qualcosa. Se tutte e quattro lasciassero l'elenco intero, il
    // comando ci sarebbe e non farebbe niente.
    r.ok(Object.values(esiti).some((e) => e.n < righe),
      `${prov}: il filtro "quando" divide (oggi ${esiti.oggi.n}, weekend `
      + `${esiti.weekend.n}, 7gg ${esiti['7'].n}, mese ${esiti.mese.n} su ${righe})`);
    // La sovrapposizione, non l'inizio: una sagra che parte venerdi' e dura
    // tre giorni e' un evento del weekend anche se e' cominciata prima. Se
    // qualcuno cambiasse il confronto in "inizia nel weekend", il weekend
    // perderebbe le sagre lunghe, che sono quelle che la gente cerca.
    r.ok(esiti.weekend.n >= esiti.oggi.n || esiti.oggi.n === 0,
      `${prov}: il weekend non e' piu' stretto di oggi`);
    await page.selectOption('#lan-quando', 'all');
    await page.waitForTimeout(200);
  }

  // 10) "SOLO GRATUITI", e la sua condizione di esistenza. Il CLAUDE.md non lo
  //     vietava sulle pagine di intenzione: diceva che prima la riga deve
  //     MOSTRARE il prezzo, se no un filtro fa sparire delle voci senza dire
  //     perche'. Quindi la prova vera non e' "il filtro funziona", e' che il
  //     filtro e la riga dicano la stessa cosa - e_gratuito() e' una funzione
  //     sola apposta.
  // CARTELLINO E ATTRIBUTO DICONO LA STESSA COSA. Vale a casella accesa e a
  // casella spenta, ed e' la prova che prende il difetto peggiore: se
  // data-free spariva dalle righe, la casella non si accendeva piu' e tutto
  // sembrava "correttamente spento". e_gratuito() e' una funzione sola apposta
  // - due letture della stessa colonna che divergono vorrebbero dire un
  // cartellino "Gratuito" su una riga che il filtro nasconde.
  const discordi = await page.evaluate(() =>
    [...document.querySelectorAll('.ev-wrap li[data-category]')]
      .filter((l) => (l.dataset.free === '1') !== !!l.querySelector('.ev-pill.is-free'))
      .length);
  r.ok(discordi === 0,
    `${prov}: cartellino "Gratuito" e data-free d'accordo su ogni riga`
    + (discordi ? `: ${discordi} discordi` : ''));

  const boxVisibile = await page.locator('#lan-gratis-box').count()
    ? await page.evaluate(() => !document.getElementById('lan-gratis-box').hidden)
    : false;
  const aPagamento = await page.evaluate(() =>
    [...document.querySelectorAll('.ev-wrap li[data-category]')]
      .filter((l) => l.dataset.free !== '1').length);
  if (boxVisibile) {
    await page.check('#lan-gratis');
    await page.waitForTimeout(250);
    const esito = await page.evaluate(() => {
      const viste = [...document.querySelectorAll('.ev-wrap li[data-category]:not([hidden])')];
      return {
        n: viste.length,
        tuttiGratis: viste.every((l) => l.dataset.free === '1'),
        tuttiColTag: viste.every((l) => !!l.querySelector('.ev-pill.is-free')),
      };
    });
    r.ok(esito.tuttiGratis, `${prov}: restano solo i gratuiti (${esito.n}/${righe})`);
    r.ok(esito.tuttiColTag,
      `${prov}: ogni riga rimasta porta il cartellino "Gratuito"`);
    r.ok(esito.n < righe, `${prov}: la casella toglie qualcosa`);
    await page.uncheck('#lan-gratis');
    await page.waitForTimeout(200);
  } else {
    // Spenta e' la risposta giusta quando toglierebbe poco: la soglia e' su
    // quello che il filtro TOGLIE, non sulla lunghezza dell'elenco. Su Asti
    // sono 8 righe (04/09/2026), e otto righe si scorrono prima di quanto si
    // trovi un comando per non vederle.
    r.ok(aPagamento < 12 || aPagamento === righe,
      `${prov}: casella spenta perche' toglierebbe solo ${aPagamento} righe`);
    r.ok(await page.evaluate(() => {
      const b = document.getElementById('lan-gratis-box');
      return !b || b.getBoundingClientRect().height === 0;
    }), `${prov}: e spenta non occupa spazio nella barra`);
  }

  // 11) LA BARRA NON E' CRESCIUTA. E' il vincolo che regge tutte le decisioni
  //     su questa barra: e' appiccicosa, quindi ogni pixel in piu' si paga su
  //     OGNI schermata dello scorrimento, non una volta. La casella sta nella
  //     prima riga accanto alla ricerca - che e' stirata e cede il posto -
  //     proprio per non far nascere una terza riga.
  r.ok(await page.locator('#lan-toolbar').evaluate((b) => b.offsetHeight) <= 120,
    `${prov}: la barra filtri resta compatta `
    + `(${await page.locator('#lan-toolbar').evaluate((b) => b.offsetHeight)}px)`);

  // 12) LE TRE SORELLE. Il link non e' cortesia: e' quello che tiene le quattro
  //    pagine provinciali a passarsi autorita' invece di contendersi la
  //    stessa query. Se sparisce, quella che perde e' la piu' nuova.
  for (const [href, chi] of [[`/sagre-provincia-${slug}.html`, 'sagre'],
                             [`/eventi/oggi-provincia-${slug}.html`, 'oggi'],
                             [`/eventi/weekend-provincia-${slug}.html`, 'weekend']]) {
    r.ok(await page.locator(`.ev-wrap a[href="${href}"]`).count() > 0,
      `${prov}: il corpo manda alla sorella ${chi}`);
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

  // ── la provincia senza finestra temporale ─────────────────────────────
  // Si provano due province su tre apposta: Cuneo perche' e' quella che ha
  // fatto nascere la pagina (48 righe su 88 con la fascia d'eta' dichiarata,
  // il caso in cui il blocco dei bambini pesa piu' dell'altro) e Alessandria
  // perche' e' il caso opposto (21 su 89) e perche' il suo nome fa cadere il
  // "| DAOP" dal title, che e' il ramo di _landing_titolo() che altrimenti
  // nessuno percorre.
  for (const [prov, slug] of [['Cuneo', 'cuneo'], ['Alessandria', 'alessandria']]) {
    r.titolo(`eventi-provincia-${slug}.html — telefono 412px`);
    ({ ctx, page } = await apri(browser, `eventi-provincia-${slug}.html`, 412));
    await provaEventiProv(r, page, prov, slug);
    await ctx.close();
  }

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
