// Always resolve the latest assignment before the camera session checks GPS.
async function refreshAttendanceOutlet() {
  const response = await fetch(attendanceUrl('/api/me'), {
    headers: {Authorization: 'Bearer ' + localStorage.getItem('token')}, cache: 'no-store'
  });
  if (!response.ok) throw new Error('Unable to refresh your assigned outlet. Please try again.');
  const latest = await response.json();
  if (!profile || latest.id !== profile.id) throw new Error('Your session changed. Refresh this page.');
  const storesResponse = await fetch(attendanceUrl('/stores'), {cache: 'no-store'});
  if (!storesResponse.ok) throw new Error('Unable to load outlet locations. Please try again.');
  const stores = await storesResponse.json();
  profile = latest;
  liveStores = stores;
  for (const store of stores) {
    if (store.latitude != null && store.longitude != null) outlets[store.name] = [Number(store.latitude), Number(store.longitude)];
  }
  if (!['ServiceManager','ACTechnicianA','ACTechnicianB','HR'].includes(profile.role)) {
    const store = stores.find(item => item.id === profile.store_id);
    if (!store || store.latitude == null || store.longitude == null) throw new Error('Your assigned outlet needs GPS coordinates. Contact Admin or HR.');
    $('outletText').textContent = 'Assigned outlet: ' + store.name + ' · 100 m geofence';
  }
}

