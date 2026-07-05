/* Banner di consenso cookie + caricamento condizionato di Google Analytics 4.
   gtag.js viene caricato SOLO dopo il consenso esplicito dell'utente: con
   rifiuto (o senza scelta) non parte alcuna richiesta verso Google e non
   viene impostato alcun cookie di misurazione. La scelta è ricordata in
   localStorage e può essere cambiata da window.daopGestisciCookie()
   (link "Gestisci preferenze cookie" nella cookie policy). */
(function () {
  var GA_ID = 'G-6M747985MC';
  var KEY = 'daop-cookie-consent'; // 'granted' | 'denied'

  window.dataLayer = window.dataLayer || [];
  function gtag() { dataLayer.push(arguments); }
  // Consent Mode v2: tutto negato finché l'utente non acconsente
  gtag('consent', 'default', {
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    analytics_storage: 'denied'
  });

  function leggiScelta() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function salvaScelta(v) {
    try { localStorage.setItem(KEY, v); } catch (e) { /* storage non disponibile */ }
  }

  var gaCaricato = false;
  function avviaAnalytics() {
    if (gaCaricato) return;
    gaCaricato = true;
    gtag('consent', 'update', { analytics_storage: 'granted' });
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
    '#daop-cookie-banner a{color:#d4793a;font-weight:600}' +
    '#daop-cookie-banner .dcb-actions{display:flex;gap:10px;flex-wrap:wrap}' +
    '#daop-cookie-banner button{cursor:pointer;border-radius:10px;padding:10px 20px;' +
    'font:inherit;font-weight:700;transition:opacity .2s}' +
    '#daop-cookie-banner button:hover{opacity:.85}' +
    '#daop-cookie-banner .dcb-ok{background:#e8954a;border:1px solid #e8954a;color:#fff}' +
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
      'Dettagli nella <a href="cookypolicy.html">cookie policy</a>.</p>' +
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
