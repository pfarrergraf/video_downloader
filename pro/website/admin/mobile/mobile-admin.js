(() => {
  const form = document.getElementById('grant-form');
  const button = document.getElementById('create-button');
  const status = document.getElementById('status');
  const result = document.getElementById('result');
  const keyEl = document.getElementById('license-key');
  const metaEl = document.getElementById('license-meta');
  const copyButton = document.getElementById('copy-button');
  const shareButton = document.getElementById('share-button');

  let currentKey = '';
  let currentLabel = '';
  let currentDays = 14;

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.classList.toggle('error', isError);
  }

  async function copyKey() {
    if (!currentKey) return;
    await navigator.clipboard.writeText(currentKey);
    copyButton.textContent = 'Kopiert';
    setTimeout(() => { copyButton.textContent = 'Kopieren'; }, 1500);
  }

  async function shareKey() {
    if (!currentKey) return;
    const text = `DownloadThat Testlizenz fuer ${currentLabel} (${currentDays} Tage):\n${currentKey}`;
    if (navigator.share) {
      await navigator.share({ title: 'DownloadThat Testlizenz', text });
      return;
    }
    await navigator.clipboard.writeText(text);
    shareButton.textContent = 'Text kopiert';
    setTimeout(() => { shareButton.textContent = 'Teilen'; }, 1500);
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    result.classList.remove('visible');
    currentKey = '';
    const label = document.getElementById('label').value.trim();
    const days = Number(document.getElementById('days').value || 14);
    if (!label) return setStatus('Bitte einen Namen eingeben.', true);
    if (!Number.isInteger(days) || days < 1 || days > 14) {
      return setStatus('Es sind nur 1 bis 14 Tage erlaubt.', true);
    }

    button.disabled = true;
    setStatus('Lizenz wird erstellt ...');
    try {
      const response = await fetch('/api/admin/mobile-tester-grant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        cache: 'no-store',
        credentials: 'same-origin',
        body: JSON.stringify({ label, expires_in_days: days }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.error || `HTTP ${response.status}`);
      }
      currentKey = body.key;
      currentLabel = body.label;
      currentDays = body.expires_in_days;
      keyEl.textContent = currentKey;
      const expires = new Date(body.expires_at * 1000);
      metaEl.textContent = `${currentLabel} · ${currentDays} Tage · bis ${expires.toLocaleString('de-DE')}`;
      result.classList.add('visible');
      setStatus('Erfolgreich erstellt. Der Rohschlüssel wird nur hier angezeigt.');
    } catch (error) {
      setStatus(`Fehler: ${error.message}`, true);
    } finally {
      button.disabled = false;
    }
  });

  copyButton.addEventListener('click', () => copyKey().catch(() => setStatus('Kopieren fehlgeschlagen.', true)));
  shareButton.addEventListener('click', () => shareKey().catch(() => setStatus('Teilen abgebrochen oder fehlgeschlagen.', true)));
})();
