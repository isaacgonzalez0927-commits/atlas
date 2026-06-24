const THEME_KEY = 'ascend_theme';

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = theme === 'dark' ? '#111827' : '#f8f9fb';
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
