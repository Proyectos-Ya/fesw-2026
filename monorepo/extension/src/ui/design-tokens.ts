/**
 * Tokens del design system de Chiripa (monorepo/frontend/src/app/globals.css), para
 * la extensión. Se declaran en el host del Shadow DOM del panel o en el :root del
 * popup, así no chocan con los estilos de Mercado Público. Sin fuentes remotas: si
 * Hanken Grotesk no está instalada, se usa la del sistema.
 */
const LIGHT = `
  --ch-bg-page: #FBF8F3;
  --ch-bg-sunken: #F3EEE6;
  --ch-surface: #FFFFFF;
  --ch-surface-inset: #F3EEE6;
  --ch-text-strong: #1B1814;
  --ch-text-body: #2A2620;
  --ch-text-muted: #60584C;
  --ch-text-subtle: #847C6E;
  --ch-border-subtle: #E8E1D5;
  --ch-border-default: #D6CDBD;
  --ch-primary: #6D8657;
  --ch-primary-hover: #556B43;
  --ch-primary-active: #3F5433;
  --ch-primary-soft: #F1F5EB;
  --ch-primary-border: #C6D8B5;
  --ch-on-primary: #FBF8F3;
  --ch-accent: #DB9E23;
  --ch-success: #2F8F5B;
  --ch-success-soft: #D6EBDC;
  --ch-success-text: #237548;
  --ch-warning: #D6960F;
  --ch-warning-soft: #F8E9C7;
  --ch-warning-text: #B07A0A;
  --ch-danger: #CC3B2E;
  --ch-danger-soft: #F7D9D4;
  --ch-danger-text: #A82E23;
  --ch-ring: rgba(109, 134, 87, 0.32);
  --ch-shadow-premium: 0 12px 32px rgba(27, 24, 20, 0.10), 0 3px 8px rgba(27, 24, 20, 0.05);
  --ch-shadow-teal: 0 8px 24px rgba(45, 79, 44, 0.18);`;

const DARK = `
  --ch-bg-page: #12110E;
  --ch-bg-sunken: #1B1814;
  --ch-surface: #1F1C18;
  --ch-surface-inset: #161411;
  --ch-text-strong: #F5F2EB;
  --ch-text-body: #DFD9CE;
  --ch-text-muted: #A69E90;
  --ch-text-subtle: #7D7567;
  --ch-border-subtle: #2E2A23;
  --ch-border-default: #3D382F;
  --ch-primary: #87A46B;
  --ch-primary-hover: #A5BF8B;
  --ch-primary-active: #6D8657;
  --ch-primary-soft: rgba(109, 134, 87, 0.20);
  --ch-primary-border: rgba(135, 164, 107, 0.35);
  --ch-on-primary: #12110E;
  --ch-success: #4ADE80;
  --ch-success-soft: rgba(20, 83, 45, 0.45);
  --ch-success-text: #86EFAC;
  --ch-warning: #FBBF24;
  --ch-warning-soft: rgba(120, 53, 15, 0.45);
  --ch-warning-text: #FCD34D;
  --ch-danger: #F87171;
  --ch-danger-soft: rgba(127, 29, 29, 0.45);
  --ch-danger-text: #FCA5A5;`;

const SHARED = `
  --ch-font-sans: "Hanken Grotesk", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --ch-font-display: "Bricolage Grotesque", "Hanken Grotesk", system-ui, -apple-system, "Segoe UI", sans-serif;
  --ch-radius-xs: 4px;
  --ch-radius-sm: 8px;
  --ch-radius-md: 12px;
  --ch-radius-lg: 16px;`;

/** Variables bajo `selector`, con modo oscuro según la preferencia del sistema. */
export function chiripaTokensCss(selector: string): string {
  return `${selector} {${SHARED}${LIGHT}
}
@media (prefers-color-scheme: dark) {
  ${selector} {${DARK}
  }
}`;
}

/** Resaltado de campos en la página de MP (fuera del Shadow DOM): valores fijos del tema claro. */
export const FIELD_HIGHLIGHT_CSS = `
[data-chiripa-field-status="filled"] {
  border: 2px solid #2F8F5B !important;
  background-color: #EEF7F1 !important;
  box-shadow: 0 0 0 3px rgba(47, 143, 91, 0.15) !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
[data-chiripa-field-status="incomplete"] {
  border: 2px solid #D6960F !important;
  background-color: #FCF4E1 !important;
  box-shadow: 0 0 0 3px rgba(214, 150, 15, 0.18) !important;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}`;
