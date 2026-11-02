/* Account credentials are sent only to same-origin endpoints and never stored locally. */
window.auraCsrfToken = null;
const authDialog = document.getElementById('accountLogin');
const authMessage = document.getElementById('accountLoginStatus');
window.showAuraLogin = function () {
  if (!authDialog.open) authDialog.showModal();
  document.getElementById('accountUsername').focus();
};
window.auraAuthReady = fetch('/api/auth/session', {cache:'no-store'}).then(response => {
  if (!response.ok) throw new Error('Could not check your session. Refresh to retry.');
  return response.json();
}).then(info => {
  window.auraCsrfToken = info.csrf_token || null;
  if (!info.auth_required) return;
  if (info.authenticated) {
    document.getElementById('accountName').textContent = info.username;
    document.getElementById('accountControls').hidden = false;
    return;
  }
  window.showAuraLogin();
  return new Promise(() => {}); // Successful login reloads the page and clears earlier account data.
}).catch(error => {
  authMessage.textContent = error.message;
  window.showAuraLogin();
  return new Promise(() => {});
});
authDialog.addEventListener('cancel', event => event.preventDefault());
document.getElementById('accountLoginForm').addEventListener('submit', async event => {
  event.preventDefault();
  const button=document.getElementById('accountLoginButton');button.disabled=true;
  authMessage.textContent='Signing in…';
  try {
    // Renew a pre-login request token after session expiry or logout.
    const check=await fetch('/api/auth/session',{cache:'no-store'});
    if (!check.ok) throw new Error('Could not contact the sign-in service. Try again.');
    const info=await check.json();
    const response=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':info.csrf_token || ''},body:JSON.stringify({username:document.getElementById('accountUsername').value,password:document.getElementById('accountPassword').value})});
    const payload=await response.json();
    if (!response.ok) throw new Error(payload.error || 'Sign-in failed. Try again.');
    document.getElementById('accountPassword').value='';location.reload();
  } catch(error) {authMessage.textContent=error.message;}
  finally {button.disabled=false;}
});
document.getElementById('accountLogout').addEventListener('click',async () => {
  try {
    const response=await fetch('/api/auth/logout',{method:'POST',headers:{'X-CSRF-Token':window.auraCsrfToken || ''}});
    if (!response.ok) throw new Error('Sign-out failed. Refresh your session and retry.');
    location.reload();
  } catch(error) { document.getElementById('accountSessionStatus').textContent=error.message; }
});
