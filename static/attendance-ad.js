(() => {
  'use strict';
  const token = localStorage.getItem('token');
  const anchor = document.querySelector('.personal-status-panel');
  if (!token || !anchor) return;
  const base = location.pathname === '/erp' || location.pathname.startsWith('/erp/') ? '/erp' : '';
  const strip = document.createElement('aside');
  strip.className = 'attendance-ad'; strip.hidden = true;
  strip.setAttribute('aria-label', 'Offer announcement'); strip.tabIndex = 0;
  const heading = document.createElement('header'); heading.className = 'attendance-ad-heading';
  const badge = document.createElement('span'); badge.className = 'attendance-ad-badge'; badge.textContent = '\u2726 SPECIAL OFFER';
  const title = document.createElement('h2'); title.className = 'attendance-ad-title';
  heading.append(badge); heading.append(title);
  const thumbnail = document.createElement('div'); thumbnail.className = 'attendance-ad-thumbnail'; thumbnail.hidden = true;
  heading.append(thumbnail);
  const track = document.createElement('div'); track.className = 'attendance-ad-track';
  const message = document.createElement('span'); message.className = 'attendance-ad-message';
  track.append(message); strip.append(heading); strip.append(track); anchor.after(strip);
  let current = '';
  let mediaURL = '', mediaKey = '';
  function clearMedia() {
    thumbnail.replaceChildren(); thumbnail.hidden = true;
    if (mediaURL) URL.revokeObjectURL(mediaURL);
    mediaURL = ''; mediaKey = '';
  }
  async function refresh() {
    try {
      const response = await fetch(base + '/api/home-ad', {
        headers: {Authorization: 'Bearer ' + token}, cache: 'no-store'
      });
      if (!response.ok) throw new Error('Advertisement unavailable');
      const ad = await response.json();
      if (!ad.visible || !ad.media_type) clearMedia();
      const titleText = ad.visible && typeof ad.title === 'string' ? ad.title.trim() : '';
      const text = ad.visible && typeof ad.message === 'string' ? ad.message.trim() : '';
      title.textContent = titleText; title.hidden = !titleText; track.hidden = !text;
      if (!text && !titleText) { strip.hidden = true; current = ''; message.textContent = ''; return; }
      if (text !== current) {
        current = text; message.textContent = text.replace(/\s*\n\s*/g, '  \u2022  ');
      }
      strip.hidden = false;
      strip.style.setProperty('--attendance-ad-width', strip.clientWidth + 'px');
      const nextKey = (ad.version || '') + ':' + ad.media_type;
      if (ad.visible && ad.media_type && nextKey !== mediaKey) {
        try {
          const result = await fetch(base + '/api/home-ad/media', {headers: {Authorization: 'Bearer ' + token}, cache: 'no-store'});
          if (!result.ok) throw new Error('Media unavailable');
          const blob = await result.blob();
          clearMedia(); mediaURL = URL.createObjectURL(blob); mediaKey = nextKey;
          const media = document.createElement(ad.media_type.startsWith('video/') ? 'video' : 'img');
          media.src = mediaURL;
          if (ad.media_type.startsWith('video/')) { media.controls = true; media.playsInline = true; media.preload = 'metadata'; }
          else media.alt = ad.title || 'Offer';
          thumbnail.append(media); thumbnail.hidden = false;
        } catch (_) { clearMedia(); }
      }
    } catch (_) { strip.hidden = true; current = ''; }
  }
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 30000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  window.addEventListener('resize', () => strip.style.setProperty('--attendance-ad-width', strip.clientWidth + 'px'));
})();
