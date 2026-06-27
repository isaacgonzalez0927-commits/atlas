const THEME_KEY = 'ascend_theme';

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme === 'dark' ? '#0d1117' : '#f6f9fc';
  const logoSrc = theme === 'dark'
    ? '/static/icon-192-dark.png'
    : '/static/icon-192-light.png';
  document.querySelectorAll('.brand-logo:not([data-logo-fixed])').forEach((img) => {
    img.src = logoSrc;
  });
  document.querySelectorAll('[data-theme-opt]').forEach((btn) => {
    const active = btn.dataset.themeOpt === theme;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
  });
}

export function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  applyTheme(saved === 'dark' ? 'dark' : 'light');

  document.querySelectorAll('[data-theme-opt]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const theme = btn.dataset.themeOpt;
      localStorage.setItem(THEME_KEY, theme);
      applyTheme(theme);
    });
  });
}
