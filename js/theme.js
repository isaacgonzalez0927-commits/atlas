const THEME_KEY = 'ascend_theme';

const LOGO_LIGHT = '/static/icon-192-light.png';
const LOGO_DARK = '/static/icon-192-dark.png';

export function applyTheme(theme) {
  const isDark = theme === 'dark';
  document.documentElement.dataset.theme = theme;

  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = isDark ? '#0d1117' : '#f6f9fc';

  document.querySelectorAll('.brand-chip-img').forEach((img) => {
    if (img.dataset.logoFixed === 'light') {
      img.src = LOGO_LIGHT;
    } else {
      img.src = isDark ? LOGO_DARK : LOGO_LIGHT;
    }
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
