(function () {
  'use strict';
  const start = Date.parse('2026-11-25T00:00:00+05:30');
  const end = Date.parse('2026-12-01T00:00:00+05:30');
  const active = (now = Date.now()) => now >= start && now < end;
  window.novIncentiveActive = active;
  const freshLogin = sessionStorage.getItem('showLoginSuccess') === '1';
  document.addEventListener('DOMContentLoaded', () => {
    const content = document.querySelector('main.content');
    if (!content || !localStorage.getItem('token')) return;
    const base = location.pathname === '/erp' || location.pathname.startsWith('/erp/') ? '/erp' : '';
    const image = base + '/static/nov-incentive-2026.png';
    const description = 'Sales incentive offer: A. O. Smith and Racold geysers: ₹500 incentive per sale, paid within 24 hours. Siemens refrigerators and washing machines: ₹1,000 incentive per sale.';
    const style = document.createElement('style');
    style.textContent = `
      .nov-offer{margin:0 0 24px;background:#090909;color:#ffe4a0;border:1px solid #d5a33b;border-radius:16px;overflow:hidden}
      .nov-offer img{display:block;width:100%;height:auto}
      .nov-offer header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:14px 18px}
      .nov-offer h2{margin:0;font-size:18px}.nov-offer p{margin:4px 0 0;font-size:13px}
      .nov-offer button,.nov-offer-dialog button{background:#f5cf72;color:#17120a;border:0;border-radius:8px;padding:10px 16px;font:700 14px sans-serif;cursor:pointer}
      .nov-offer-dialog{width:min(1100px,96vw);max-height:92vh;padding:0;border:1px solid #d5a33b;border-radius:16px;background:#090909;color:#ffe4a0;overflow:auto}
      .nov-offer-dialog::backdrop{background:#000b}.nov-offer-dialog img{display:block;width:100%;height:auto}
      .nov-offer-dialog header{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:14px 18px}
      .nov-offer-dialog h2{margin:0;font-size:18px}.nov-offer-dialog p{margin:4px 0 0;font-size:13px}
      .nov-offer-dialog .offer-summary{padding:0 18px 18px;line-height:1.6}
    `;
    document.head.appendChild(style);
    let banner, dialog, popupTimer;
    function sync() {
      if (!active()) {
        clearTimeout(popupTimer);
        banner?.remove();
        if (dialog?.open) dialog.close();
        dialog?.remove();
        banner = dialog = null;
        return;
      }
      if (banner) return;
      banner = document.createElement('section');
      banner.className = 'nov-offer';
      banner.setAttribute('aria-label', 'November sales incentive offer');
      banner.innerHTML = '<header><div><h2>Sales Incentive Offer</h2><p>25–30 November 2026 · India time</p></div><button type="button">View offer</button></header>';
      const poster = document.createElement('img');
      poster.src = image;
      poster.alt = description;
      poster.width = 1774;
      poster.height = 887;
      banner.appendChild(poster);
      content.prepend(banner);
      dialog = document.createElement('dialog');
      dialog.className = 'nov-offer-dialog';
      dialog.setAttribute('aria-labelledby', 'novOfferTitle');
      dialog.innerHTML = '<header><div><h2 id="novOfferTitle">Sales Incentive Offer</h2><p>25–30 November 2026 · India time</p></div><button type="button" autofocus>Close</button></header>';
      dialog.appendChild(poster.cloneNode());
      const summary = document.createElement('p');
      summary.className = 'offer-summary';
      summary.textContent = description;
      dialog.appendChild(summary);
      document.body.appendChild(dialog);
      const open = () => { if (active() && !dialog.open) dialog.showModal(); };
      banner.querySelector('button').addEventListener('click', open);
      dialog.querySelector('button').addEventListener('click', () => dialog.close());
      // Let the existing sign-in success animation finish first.
      popupTimer = setTimeout(open, freshLogin ? 2000 : 0);
    }
    sync();
    setInterval(sync, 1000);
    document.addEventListener('visibilitychange', sync);
  });
})();
