(() => {
  'use strict';
  const base = location.pathname === '/erp' || location.pathname.startsWith('/erp/') ? '/erp' : '';
  const endpoint = base + '/api/home-ad';
  const token = localStorage.getItem('token');
  if (!token) return;
  let saved = {}, savedMedia = '', draftMedia = '', busy = false;
  const banner = document.createElement('section');
  banner.className = 'home-ad'; banner.hidden = true; banner.setAttribute('aria-label', 'Advertisement');
  document.querySelector('.infinity-stage').before(banner);
  async function request(path = '', options = {}) {
    const response = await fetch(endpoint + path, {...options, headers: {Authorization: 'Bearer ' + token}, cache: 'no-store'});
    if (!response.ok) {
      let detail = 'Unable to update advertisement. Please try again.';
      try { const data = await response.json(); if (typeof data.detail === 'string') detail = data.detail; } catch (_) {}
      throw new Error(detail);
    }
    return path === '/media' ? response.blob() : response.json();
  }
  function draw(target, ad, mediaURL) {
    target.replaceChildren();
    if (ad.title || ad.message || ad.media_type) {
      const header = document.createElement('header'), badge = document.createElement('span');
      header.className = 'home-ad-heading'; badge.className = 'home-ad-badge';
      badge.textContent = '\u2726 SPECIAL OFFER'; header.append(badge);
      if (ad.title) { const h = document.createElement('h2'); h.textContent = ad.title; header.append(h); }
      target.append(header);
    }
    if (ad.media_type && mediaURL) {
      const media = document.createElement(ad.media_type.startsWith('video/') ? 'video' : 'img');
      media.className = 'home-ad-media'; media.src = mediaURL;
      // Preserve the complete media at its original proportions.
      media.style.cssText = 'display:block;width:100%;max-width:100%;height:100%;max-height:100%;object-fit:contain;object-position:center;border:0;border-radius:0;';
      if (media.tagName === 'VIDEO') { media.controls = true; media.playsInline = true; media.preload = 'metadata'; }
      else media.alt = ad.title || 'Advertisement';
      const frame = document.createElement('div'); frame.className = 'home-ad-media-frame';
      frame.style.cssText = 'display:block;width:100%;padding:0;height:var(--ad-media-height,240px);overflow:hidden;';
      frame.append(media); target.append(frame);
    }
    if (ad.message) {
      const track = document.createElement('div'), text = document.createElement('div');
      track.className = 'home-ad-track'; track.tabIndex = 0; track.setAttribute('aria-label', ad.message);
      text.className = 'home-ad-message'; text.textContent = ad.message.replace(/\n/g, '   •   ');
      track.append(text); target.append(track);
      requestAnimationFrame(() => track.style.setProperty('--ad-width', track.clientWidth + 'px'));
    }
  }
  async function load() {
    const next = await request();
    if (next.version && next.version === saved.version && next.media_type === saved.media_type) { saved = next; banner.hidden = !saved.visible; return; }
    let url = '';
    if (next.media_type) url = URL.createObjectURL(await request('/media'));
    if (savedMedia) URL.revokeObjectURL(savedMedia);
    saved = next; savedMedia = url;
    draw(banner, saved, savedMedia); banner.hidden = !saved.visible;
  }
  if (['Admin', 'HR'].includes(localStorage.getItem('role'))) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'ads-button'; button.textContent = '+ Ads';
    document.querySelector('.content-head').append(button);
    const editor = document.createElement('dialog'); editor.className = 'ads-editor'; editor.setAttribute('aria-labelledby', 'adsTitle');
    editor.innerHTML = `<header><h2 id="adsTitle">ADS</h2><button type="button" data-close aria-label="Close advertisement editor">&times;</button></header>
      <form><label for="adTitle">Ad title</label><input id="adTitle" type="text" maxlength="160" placeholder="e.g. Sales incentive offer">
      <label for="adMessage">Scrolling message · right to left</label><textarea id="adMessage" maxlength="4000" placeholder="Write your offer or announcement here..."></textarea>
      <label for="adMedia">Upload image or video</label><input id="adMedia" type="file" accept="image/jpeg,image/png,image/gif,image/webp,image/avif,video/mp4,video/webm,video/ogg,video/quicktime">
      <p>Images: JPG, PNG, GIF, WebP, AVIF. Videos: MP4, WebM, OGG, MOV. Maximum 50 MB.</p>
      <label><input id="adRemove" type="checkbox"> Remove saved media</label>
      <label><input id="adVisible" type="checkbox"> Show advertisement on home page</label>
      <div class="ads-preview"><label>Preview</label><section class="home-ad" id="adPreview"></section></div>
      <div class="ads-actions"><button type="submit" class="ads-save">Save advertisement</button><button type="button" data-toggle>Hide advertisement</button><button type="button" class="ads-clear" data-clear>Clear advertisement</button></div>
      <div class="ads-status" role="status" aria-live="polite"></div></form>`;
    document.body.append(editor);
    const field = id => editor.querySelector('#' + id), status = editor.querySelector('.ads-status');
    function preview() {
      const file = field('adMedia').files[0];
      draw(field('adPreview'), {title:field('adTitle').value, message:field('adMessage').value, media_type:file?.type || (!field('adRemove').checked && saved.media_type)}, draftMedia || (!field('adRemove').checked && savedMedia));
    }
    function populate() {
      if (draftMedia) URL.revokeObjectURL(draftMedia); draftMedia = '';
      field('adTitle').value = saved.title || ''; field('adMessage').value = saved.message || '';
      field('adMedia').value = ''; field('adRemove').checked = false; field('adVisible').checked = saved.version ? saved.visible : true;
      editor.querySelector('[data-toggle]').textContent = saved.visible ? 'Hide advertisement' : 'Show advertisement'; preview();
    }
    async function action(work) {
      if (busy) return; busy = true; status.textContent = 'Saving…';
      editor.querySelectorAll('button').forEach(b => b.disabled = true);
      try { await work(); await load(); populate(); status.textContent = 'Advertisement updated successfully.'; }
      catch (error) { status.textContent = error.message; }
      finally { busy = false; editor.querySelectorAll('button').forEach(b => b.disabled = false); }
    }
    button.onclick = async () => {
      status.textContent = 'Loading…'; editor.showModal();
      try { await load(); populate(); status.textContent = ''; } catch (error) { status.textContent = error.message; }
    };
    editor.querySelector('[data-close]').onclick = () => editor.close();
    editor.onclick = event => {
      if (event.target !== editor) return;
      const bounds = editor.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right ||
          event.clientY < bounds.top || event.clientY > bounds.bottom) editor.close();
    };
    editor.querySelector('form').addEventListener('input', preview);
    field('adMedia').addEventListener('change', () => {
      if (draftMedia) URL.revokeObjectURL(draftMedia); draftMedia = '';
      const file = field('adMedia').files[0];
      if (file && file.size > 50 * 1024 * 1024) { field('adMedia').value = ''; status.textContent = 'Please choose a file up to 50 MB.'; }
      else if (file) { draftMedia = URL.createObjectURL(file); status.textContent = ''; }
      preview();
    });
    editor.querySelector('form').onsubmit = event => {
      event.preventDefault();
      const data = new FormData();
      data.set('title', field('adTitle').value); data.set('message', field('adMessage').value);
      data.set('visible', field('adVisible').checked); data.set('remove_media', field('adRemove').checked);
      if (field('adMedia').files[0]) data.set('media', field('adMedia').files[0]);
      action(() => request('', {method:'PUT', body:data}));
    };
    editor.querySelector('[data-toggle]').onclick = () => { const data = new FormData(); data.set('visible', !saved.visible); action(() => request('/visibility', {method:'PATCH', body:data})); };
    editor.querySelector('[data-clear]').onclick = () => {
      if (confirm('Clear the saved advertisement, including its text and media?')) action(() => request('', {method:'DELETE'}));
    };
  }
  load().catch(error => console.error('Advertisement:', error.message));
  // Refresh visibility for people who leave the home page open.
  setInterval(() => { if (!document.hidden && !busy && !document.querySelector('.ads-editor[open]')) load().catch(() => {}); }, 60000);
})();
