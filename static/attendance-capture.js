// A punch belongs to one explicit camera session. Never replay cached punches.
(() => {
  let session = 0, active = null, submitting = false;
  const currentDay = () => new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Kolkata'}).format(new Date());
  function validGps(gps) {
    const c = gps?.coords;
    return c && Number.isFinite(gps.timestamp) && Date.now() - gps.timestamp >= -5000 &&
      Date.now() - gps.timestamp <= 60000 && Number.isFinite(c.latitude) && Math.abs(c.latitude) <= 90 &&
      Number.isFinite(c.longitude) && Math.abs(c.longitude) <= 180 &&
      Number.isFinite(c.accuracy) && c.accuracy >= 0 && c.accuracy <= 200;
  }
  const stopCamera = closeModal;
  closeModal = function () {
    session++;
    active = null;
    $('camera').onloadeddata = null;
    stopCamera();
  };
  $('cancel').onclick = closeModal;
  beginAction = async function (action) {
    if (submitting || active || !profile) return;
    if (!['checkin', 'checkout'].includes(action)) return;
    if (typeof today !== 'undefined' && currentDay() !== today) { window.location.reload(); return; }
    closeModal();
    const id = session;
    active = {id, action, userId: profile.id, day:currentDay(), token:localStorage.getItem('token')};
    $('modal').classList.add('show');
    $('modalText').textContent = 'Preparing location and camera...';
    try {
      if (!navigator.onLine) throw new Error('Connect to the internet before marking attendance.');
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera is unavailable. Open the app over HTTPS and allow camera access.');
      const video = $('camera');
      const ready = () => {
        if (id !== session || video.readyState < 2 || !video.videoWidth || !video.videoHeight) return;
        if (!active.gps) {
          $('modalText').textContent = 'Camera ready. Verifying your location...';
          return;
        }
        $('capture').disabled = false;
        $('modalText').textContent = action === 'checkout' ? 'Look at the camera, then tap Capture & Punch Out.' : 'Look at the camera, then tap Capture & Punch In.';
        $('capture').textContent = action === 'checkout' ? 'Capture & Punch Out' : 'Capture & Punch In';
      };
      // Start the camera on the click, without waiting for a precise GPS fix.
      const cameraReady = (async () => {
        const media = await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'user'},width:{ideal:720},height:{ideal:960}},audio:false});
        if (id !== session) { media.getTracks().forEach(track => track.stop()); return; }
        stream = media;
        video.srcObject = media;
        video.style.display = 'block';
        video.onloadeddata = ready;
        await video.play();
        ready();
      })();
      const locationReady = (async () => {
        // Reuse a recent page/tracking fix instead of forcing another GPS acquisition.
        // Leave at least 30 seconds of the validity window for taking the selfie.
        const cached = validGps(position) && Date.now() - position.timestamp <= 30000 ? position : null;
        const gps = cached || await new Promise((resolve, reject) => {
          if (!navigator.geolocation) return reject(new Error('Location is unavailable.'));
          navigator.geolocation.getCurrentPosition(resolve, reject, {enableHighAccuracy:true, timeout:15000, maximumAge:30000});
        });
        if (id !== session) return;
        if (!validGps(gps)) throw new Error('GPS reading is invalid or inaccurate. Please enable precise location and retry.');
        position = gps;
        const outlet = assignedOutlet(), distance = meters(gps.coords.latitude, gps.coords.longitude, outlets[outlet]);
        const anywhere = ['ServiceManager','ACTechnicianA','ACTechnicianB','HR'].includes(profile.role);
        if (!anywhere && distance > 100) throw new Error('Verify your GPS location within the allowed outlet area and try again.');
        active.gps = gps;
        active.distance = distance;
        ready();
      })();
      await Promise.all([cameraReady, locationReady]);
    } catch (error) {
      if (id !== session) return;
      closeModal();
      setGps(error.message || 'Unable to prepare camera or location. Please try again.', 'bad');
    }
  };
  $('mark').onclick = () => beginAction('checkin');
  checkoutButton.onclick = () => beginAction('checkout');
  $('capture').onclick = async function () {
    const video = $('camera'), current = active;
    if (!current || submitting || $('capture').disabled || document.hidden ||
        current.userId !== profile?.id || video.srcObject !== stream ||
        !stream?.getVideoTracks().some(track => track.readyState === 'live' && !track.muted) ||
        video.readyState < 2 || !video.videoWidth || !video.videoHeight) return;
    submitting = true;
    $('capture').disabled = true;
    try {
      if (!navigator.onLine) throw new Error('Connect to the internet and capture a new selfie.');
      if (current.token !== localStorage.getItem('token')) throw new Error('Account changed. Refresh before marking attendance.');
      if (current.day !== currentDay()) throw new Error('The attendance date changed. Refresh and capture again.');
      if (!validGps(current.gps)) throw new Error('Location expired. Please reopen the camera and capture again.');
      const canvas = document.createElement('canvas');
      // Bound the upload itself, preserving aspect ratio without upscaling.
      const scale = Math.min(1, 360 / video.videoWidth, 480 / video.videoHeight);
      canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
      canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
      canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
      const payload = {action:current.action, captured_at:new Date().toISOString(),
        selfie:canvas.toDataURL('image/jpeg', .55), latitude:current.gps.coords.latitude,
        longitude:current.gps.coords.longitude, accuracy_m:current.gps.coords.accuracy,
        distance_m:current.distance};
      closeModal();
      // Ignore history requests started before this write.
      if (typeof attendanceRefreshVersion !== 'undefined') attendanceRefreshVersion++;
      $('sync').textContent = 'Saving attendance...';
      const response = await fetch('/api/attendance', {method:'POST',
        signal:AbortSignal.timeout(30000),
        headers:{Authorization:'Bearer '+current.token,'Content-Type':'application/json'},
        body:JSON.stringify(payload)});
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || 'Attendance was not saved. Refresh and try again.');
      if (!await syncAttendanceHistory()) {
        $('sync').textContent = 'Attendance saved. Refresh to load the latest record.';
        $('sync').className = 'badge warn';
      }
    } catch (error) {
      closeModal();
      // A lost response may have committed. Refresh before a user retries;
      // do not silently retry with a stored image or create a local punch.
      await syncAttendanceHistory();
      $('sync').textContent = error.message || 'Unable to confirm attendance. Refresh to check before trying again.';
      $('sync').className = 'badge bad';
    } finally { submitting = false; }
  };
})();
