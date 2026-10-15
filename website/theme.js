(() => {
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let saved;
  try { saved = localStorage.getItem('browser-selector-theme'); } catch {}
  const apply = theme => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]').content = theme === 'dark' ? '#11161e' : '#fafbfc';
    const button = document.querySelector('.theme-toggle');
    if (button) button.setAttribute('aria-label', `Use ${theme === 'dark' ? 'light' : 'dark'} theme`);
  };
  apply(saved || (system.matches ? 'dark' : 'light'));
  system.addEventListener('change', event => { if (!saved) apply(event.matches ? 'dark' : 'light'); });
  document.addEventListener('DOMContentLoaded', () => {
    apply(document.documentElement.dataset.theme);
    document.querySelector('.theme-toggle').addEventListener('click', () => {
      saved = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('browser-selector-theme', saved); } catch {}
      apply(saved);
    });
  });
})();
