const THEME_KEY = 'ascend_theme';

const LOGO_DEFAULT = '/static/logo.svg';
const LOGO_ON_DARK = '/static/logo-light.svg';

export function applyTheme(theme) {
  const isDark = theme === 'dark';
  document.documentElement.dataset.theme = theme;

  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = isDark ? '#0d1117' : '#f6f9fc';

  const logoSrc = isDark ? LOGO_ON_DARK : LOGO_DEFAULT;
  document.querySelectorAll('.brand-logo:not(.brand-logo--sidebar)').forEach((img) => {
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
