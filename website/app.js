const status = document.querySelector('#preview-status');
document.querySelectorAll('.profiles button').forEach(button => {
  button.addEventListener('click', () => {
    status.textContent = `In the app, this opens the link in ${button.dataset.browser} → ${button.dataset.profile}.`;
  });
});
const copy = document.querySelector('#copy-url');
const copyIcon = copy.innerHTML;
let copyTimer;
copy.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText('https://example.com');
    copy.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg>';
    copy.setAttribute('aria-label', 'URL copied');
    status.textContent = 'Example URL copied.';
    clearTimeout(copyTimer);
    copyTimer = setTimeout(() => { copy.innerHTML = copyIcon; copy.setAttribute('aria-label', 'Copy example URL'); }, 2500);
  } catch { status.textContent = 'Copy this example URL: https://example.com'; }
});
