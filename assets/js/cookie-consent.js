/* Banner di consenso cookie + caricamento condizionato di Google Analytics 4.
   gtag.js viene caricato SOLO dopo il consenso esplicito dell'utente: con
   rifiuto (o senza scelta) non parte alcuna richiesta verso Google e non
   viene impostato alcun cookie di misurazione. La scelta è ricordata in
   localStorage e può essere cambiata da window.daopGestisciCookie()
   (link "Gestisci preferenze cookie" nella cookie policy).

   QUESTO FILE E' L'UNICO PUNTO IN CUI GA4 VIENE INIZIALIZZATO.
   Fino al 12/08/2026 il `gtag('config', ...)` stava scritto a mano dentro
   dodici pagine e mancava dappertutto altrove: questo script caricava
   gtag.js ma non gli diceva mai quale proprieta' misurare, quindi le ~280
   pagine generate (tutte le schede /eventi/, le pagine comune, oggi,
   weekend, le provinciali, zone, metodo, centri estivi) caricavano la
   libreria e non mandavano nessun page_view. Da qui il buco fra i clic di
   Search Console e gli utenti in GA4.
   Il `config` sta ora qui, una volta sola: chi include questo file e'
   tracciato, e non c'e' modo di dimenticarsene su una pagina nuova.
   Corollario: NON riaggiungere un blocco gtag inline nelle pagine, sarebbe
   una seconda inizializzazione e un secondo page_view. */
(function () {
  var GA_ID = 'G-6M747985MC';
  var KEY = 'daop-cookie-consent'; // 'granted' | 'denied'

  window.dataLayer = window.dataLayer || [];
  function gtag() { dataLayer.push(arguments); }
  window.gtag = window.gtag || gtag;
  // Consent Mode v2: tutto negato finché l'utente non acconsente
  gtag('consent', 'default', {
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    analytics_storage: 'denied'
  });

  /* La home e' raggiungibile come "/" (canonical, sitemap, link da Google) e
     come "/index.html" (la nav del sito la scrive cosi' in ~290 punti). Per
     GA4 sono due pagine diverse e la home risultava spezzata in due righe.
     Si normalizza qui, nel parametro mandato a GA4: nessun redirect, nessun
     link cambiato, nessun rischio lato SEO — il canonical era gia' "/". */
  function percorso() {
    return location.pathname.replace(/\/index\.html$/i, '/') || '/';
  }


  function leggiScelta() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function salvaScelta(v) {
    try { localStorage.setItem(KEY, v); } catch (e) { /* storage non disponibile */ }
  }

  /* Lo leggono gli altri script (daop-track.js) prima di mandare qualunque
     evento. Serve perche' `gtag` come funzione esiste sempre — e' lo stub che
     accoda in dataLayer — quindi "typeof gtag === 'function'" non dice se
     l'utente ha acconsentito. Senza questo controllo un clic fatto dopo il
     "Rifiuta" restava in coda in dataLayer e, se piu' tardi l'utente cambiava
     idea e accettava, gtag.js svuotava la coda e lo spediva lo stesso: un
     evento raccolto prima del consenso. */
  window.daopConsensoAnalytics = false;

  var gaCaricato = false;
  function avviaAnalytics() {
    if (gaCaricato) return;
    gaCaricato = true;
    window.daopConsensoAnalytics = true;

    /* L'ORDINE DI QUESTE TRE COSE NON E' CASUALE.
       gtag.js, quando si carica, esegue la coda di dataLayer nell'ordine in
       cui e' stata riempita. Il `config` e' quello che fa partire il
       page_view, quindi deve stare DOPO l'aggiornamento del consenso.
       Tenendo il `config` a inizio pagina la coda diventava
       default(denied) -> config -> update(granted), e il page_view usciva
       col parametro gcs=G100, cioe' analytics_storage negato: GA4 lo
       riceveva e lo scartava. Si vedeva un buco preciso — nessun page_view,
       ma i clic (spediti dopo, quindi con gcs=G101) arrivavano tutti.
       Verificato il 12/08/2026 leggendo le richieste a /g/collect. */
    gtag('consent', 'update', { analytics_storage: 'granted' });
    gtag('js', new Date());
    gtag('config', GA_ID, {
      page_path: percorso(),
      page_location: location.origin + percorso() + location.search
    });

    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    document.head.appendChild(s);
  }

  var CSS =
    '#daop-cookie-banner{position:fixed;left:16px;right:16px;bottom:16px;z-index:99999;' +
    'max-width:480px;margin:0 auto;background:#fdf8f3;color:#2d4a5c;' +
    'border:1px solid rgba(45,74,92,0.15);border-radius:16px;' +
    'box-shadow:0 12px 40px rgba(30,51,66,0.25);padding:20px 22px;' +
    'font-family:"DM Sans",system-ui,sans-serif;font-size:0.92rem;line-height:1.5}' +
    '#daop-cookie-banner p{margin:0 0 14px}' +
    '#daop-cookie-banner a{color:#ad5e16;font-weight:600}' +
    '#daop-cookie-banner .dcb-actions{display:flex;gap:10px;flex-wrap:wrap}' +
    '#daop-cookie-banner button{cursor:pointer;border-radius:10px;padding:10px 20px;' +
    'font:inherit;font-weight:700;transition:opacity .2s}' +
    '#daop-cookie-banner button:hover{opacity:.85}' +
    '#daop-cookie-banner .dcb-ok{background:#e8954a;border:1px solid #e8954a;color:#1a2d3a}' +
    '#daop-cookie-banner .dcb-no{background:transparent;border:1px solid rgba(45,74,92,0.35);color:#2d4a5c}';

  function mostraBanner() {
    if (document.getElementById('daop-cookie-banner')) return;
    var style = document.createElement('style');
    style.textContent = CSS;
    document.head.appendChild(style);

    var box = document.createElement('div');
    box.id = 'daop-cookie-banner';
    box.setAttribute('role', 'region');
    box.setAttribute('aria-label', 'Informativa cookie');
    box.innerHTML =
      '<p><strong>Cookie e statistiche.</strong> Usiamo Google Analytics, solo se acconsenti, ' +
      'per capire come viene usato il sito e migliorarlo. Nessuna pubblicità, nessuna profilazione. ' +
      'Dettagli nella <a href="/cookie-policy.html">cookie policy</a>.</p>' +
      '<div class="dcb-actions">' +
      '<button type="button" class="dcb-ok">Accetta</button>' +
      '<button type="button" class="dcb-no">Rifiuta</button>' +
      '</div>';

    box.querySelector('.dcb-ok').addEventListener('click', function () {
      salvaScelta('granted');
      box.remove();
      avviaAnalytics();
    });
    box.querySelector('.dcb-no').addEventListener('click', function () {
      salvaScelta('denied');
      box.remove();
    });
    document.body.appendChild(box);
  }

  function init() {
    var scelta = leggiScelta();
    if (scelta === 'granted') {
      avviaAnalytics();
    } else if (scelta !== 'denied') {
      mostraBanner();
    }
  }

  // riapre il banner per cambiare la scelta (usato dalla cookie policy)
  window.daopGestisciCookie = function () {
    try { localStorage.removeItem(KEY); } catch (e) {}
    mostraBanner();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
