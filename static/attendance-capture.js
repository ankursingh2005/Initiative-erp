// A punch belongs to one explicit camera session. Never replay cached punches.
(() => {
  let session = 0, active = null, submitting = false;
  const stopCamera = closeModal;
  closeModal = function () {
    session++;
    active = null;
    stopCamera();
  };
  $('cancel').onclick = closeModal;
  beginAction = async function (action) {
    if (submitting || active || !profile) return;
    closeModal();
    const id = session;
    active = {id, action, userId: profile.id};
    $('modal').classList.add('show');
    $('modalText').textContent = 'Preparing location and camera...';
    try {
      if (!navigator.onLine) throw new Error('Connect to the internet before marking attendance.');
      const gps = await new Promise((resolve, reject) => {
        if (!navigator.geolocation) return reject(new Error('Location is unavailable.'));
        navigator.geolocation.getCurrentPosition(resolve, reject, {enableHighAccuracy:true, timeout:15000, maximumAge:0});
      });
      if (id !== session) return;
      position = gps;
      const outlet = assignedOutlet(), distance = meters(gps.coords.latitude, gps.coords.longitude, outlets[outlet]);
      const anywhere = ['ServiceManager','ACTechnicianA','ACTechnicianB','HR'].includes(profile.role);
      if (gps.coords.accuracy > 200 || (!anywhere && distance > 100)) throw new Error('Verify your GPS location within the allowed outlet area and try again.');
      const media = await navigator.mediaDevices.getUserMedia({video:{facingMode:{ideal:'user'},width:{ideal:720},height:{ideal:960}},audio:false});
      if (id !== session) { media.getTracks().forEach(track => track.stop()); return; }
      stream = media;
      const video = $('camera');
      video.srcObject = media;
      video.style.display = 'block';
      await video.play();
      if (id !== session) return;
      const ready = () => {
        if (id !== session || video.readyState < 2 || !video.videoWidth || !video.videoHeight) return;
        $('capture').disabled = false;
        $('modalText').textContent = action === 'checkout' ? 'Look at the camera, then tap Capture & Punch Out.' : 'Look at the camera, then tap Capture & Punch In.';
        $('capture').textContent = action === 'checkout' ? 'Capture & Punch Out' : 'Capture & Punch In';
      };
      video.onloadeddata = ready;
      ready();
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
        !stream?.getVideoTracks().some(track => track.readyState === 'live') ||
        video.readyState < 2 || !video.videoWidth || !video.videoHeight) return;
    submitting = true;
    $('capture').disabled = true;
    try {
      if (!navigator.onLine) throw new Error('Connect to the internet and capture a new selfie.');
      if (!position || Date.now() - position.timestamp > 60000) throw new Error('Location expired. Please reopen the camera and capture again.');
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth; canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
      const payload = {action:current.action, captured_at:new Date().toISOString(),
        selfie:canvas.toDataURL('image/jpeg', .75), latitude:position.coords.latitude,
        longitude:position.coords.longitude, accuracy_m:position.coords.accuracy,
        distance_m:meters(position.coords.latitude, position.coords.longitude, outlets[assignedOutlet()])};
      closeModal();
      $('sync').textContent = 'Saving attendance...';
      const response = await fetch('/api/attendance', {method:'POST',
        headers:{Authorization:'Bearer '+localStorage.getItem('token'),'Content-Type':'application/json'},
        body:JSON.stringify(payload)});
      const result = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(result.detail || 'Attendance was not saved. Refresh and try again.');
      await syncAttendanceHistory();
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
