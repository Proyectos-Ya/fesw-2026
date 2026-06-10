import React from 'react';

/**
 * Thin wrapper around Lucide icons. Requires the Lucide UMD script to be
 * loaded on the page (https://unpkg.com/lucide@latest). Renders an <i> that
 * Lucide hydrates into an inline SVG, so icons inherit `currentColor`.
 */
export function Icon({ name, size = 20, strokeWidth = 2, color = 'currentColor', style = {}, ...rest }) {
  const ref = React.useRef(null);

  React.useEffect(() => {
    const el = ref.current;
    if (!el || typeof window === 'undefined' || !window.lucide) return;
    el.innerHTML = '';
    const node = document.createElement('i');
    node.setAttribute('data-lucide', name);
    el.appendChild(node);
    try { window.lucide.createIcons({ attrs: { width: size, height: size, 'stroke-width': strokeWidth } }); } catch (e) {}
  }, [name, size, strokeWidth]);

  return (
    <span
      ref={ref}
      aria-hidden="true"
      style={{ display: 'inline-flex', width: size, height: size, color, flex: 'none', ...style }}
      {...rest}
    />
  );
}
