import { chiripaTokensCss } from "./design-tokens";

/** Estilos del panel de postulación (Shadow DOM), con los tokens del design system. */
export const POSTULATION_PANEL_CSS = `${chiripaTokensCss(":host")}
:host {
  all: initial;
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 2147483647;
  font-family: var(--ch-font-sans);
  color: var(--ch-text-body);
  -webkit-font-smoothing: antialiased;
}
.panel {
  width: 336px;
  background: var(--ch-surface);
  color: var(--ch-text-body);
  border: 1px solid var(--ch-border-subtle);
  border-radius: var(--ch-radius-lg);
  box-shadow: var(--ch-shadow-premium);
  padding: 16px;
  box-sizing: border-box;
  font-size: 13px;
  line-height: 1.45;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--ch-font-display);
  font-size: 15px;
  font-weight: 700;
  color: var(--ch-text-strong);
  letter-spacing: -0.01em;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ch-primary);
  box-shadow: 0 0 0 3px var(--ch-primary-soft);
}
.close-btn {
  background: none;
  border: none;
  color: var(--ch-text-subtle);
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  padding: 6px;
  border-radius: var(--ch-radius-sm);
}
.close-btn:hover {
  color: var(--ch-text-strong);
  background: var(--ch-bg-sunken);
}
.tender-info {
  font-size: 12px;
  color: var(--ch-text-muted);
  margin-bottom: 12px;
  background: var(--ch-surface-inset);
  border: 1px solid var(--ch-border-subtle);
  padding: 10px 12px;
  border-radius: var(--ch-radius-md);
}
.tender-code {
  display: block;
  font-weight: 700;
  color: var(--ch-primary-hover);
  margin-bottom: 2px;
}
.metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 12px;
}
.metric-box {
  padding: 10px;
  border-radius: var(--ch-radius-md);
  text-align: center;
  border: 1px solid var(--ch-border-subtle);
  background: var(--ch-surface-inset);
}
.metric-num {
  font-family: var(--ch-font-display);
  font-size: 20px;
  font-weight: 800;
  line-height: 1.1;
}
.metric-num.green {
  color: var(--ch-success-text);
}
.metric-num.amber {
  color: var(--ch-warning-text);
}
.metric-label {
  font-size: 11px;
  color: var(--ch-text-muted);
  margin-top: 2px;
}
.notice {
  background: var(--ch-danger-soft);
  border: 1px solid var(--ch-danger);
  color: var(--ch-danger-text);
  border-radius: var(--ch-radius-sm);
  padding: 8px 10px;
  font-size: 12px;
  margin-bottom: 10px;
}
.annex-box {
  background: var(--ch-primary-soft);
  border: 1px solid var(--ch-primary-border);
  color: var(--ch-text-body);
  border-radius: var(--ch-radius-md);
  padding: 10px 12px;
  font-size: 12px;
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.pending-list {
  margin: 0 0 12px;
  padding: 8px 10px 8px 26px;
  font-size: 12px;
  color: var(--ch-warning-text);
  background: var(--ch-warning-soft);
  border-radius: var(--ch-radius-sm);
}
.pending-list li + li {
  margin-top: 2px;
}
.warning-box {
  background: var(--ch-surface-inset);
  border: 1px solid var(--ch-border-subtle);
  border-left: 3px solid var(--ch-accent);
  border-radius: var(--ch-radius-sm);
  padding: 8px 10px;
  font-size: 11px;
  color: var(--ch-text-muted);
  margin-bottom: 12px;
}
.actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.btn {
  display: block;
  width: 100%;
  padding: 9px 14px;
  font-family: var(--ch-font-sans);
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--ch-radius-sm);
  cursor: pointer;
  text-align: center;
  box-sizing: border-box;
  transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}
.btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 3px var(--ch-ring);
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-outline {
  background: transparent;
  border: 1px solid var(--ch-border-default);
  color: var(--ch-text-body);
}
.btn-outline:hover {
  background: var(--ch-primary-soft);
  border-color: var(--ch-primary-border);
  color: var(--ch-primary-hover);
}
.annex-box .btn-outline {
  background: var(--ch-primary);
  border-color: var(--ch-primary);
  color: var(--ch-on-primary);
  box-shadow: var(--ch-shadow-teal);
}
.annex-box .btn-outline:hover {
  background: var(--ch-primary-hover);
  border-color: var(--ch-primary-hover);
  color: var(--ch-on-primary);
}
`;
