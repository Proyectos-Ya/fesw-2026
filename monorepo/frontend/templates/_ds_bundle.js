/* @ds-bundle: {"format":3,"namespace":"ProyectosYaDesignSystem_1dd038","components":[{"name":"Icon","sourcePath":"components/core/Icon.jsx"},{"name":"Badge","sourcePath":"components/feedback/Badge.jsx"},{"name":"MatchMeter","sourcePath":"components/feedback/MatchMeter.jsx"},{"name":"Tag","sourcePath":"components/feedback/Tag.jsx"},{"name":"Button","sourcePath":"components/forms/Button.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"IconButton","sourcePath":"components/forms/IconButton.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Switch","sourcePath":"components/forms/Switch.jsx"},{"name":"Avatar","sourcePath":"components/layout/Avatar.jsx"},{"name":"Card","sourcePath":"components/layout/Card.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"}],"sourceHashes":{"components/core/Icon.jsx":"56da11a44058","components/feedback/Badge.jsx":"4127142a60c3","components/feedback/MatchMeter.jsx":"4a9e5ae4351d","components/feedback/Tag.jsx":"24c24c6fa4a4","components/forms/Button.jsx":"5e2e9208e3df","components/forms/Checkbox.jsx":"5566af7d5bdb","components/forms/IconButton.jsx":"be410900dd9b","components/forms/Input.jsx":"eefe8ecddf07","components/forms/Select.jsx":"eeccb277e592","components/forms/Switch.jsx":"2813e72cef76","components/layout/Avatar.jsx":"4cd047d32a33","components/layout/Card.jsx":"37b5a8f4de58","components/navigation/Tabs.jsx":"343adb8ea204","ui_kits/app/AppShell.jsx":"897907d0126f","ui_kits/app/DashboardScreen.jsx":"8c88a9e7cc5f","ui_kits/app/LicitacionCard.jsx":"d17a12cc75a3","ui_kits/app/LicitacionDetailScreen.jsx":"814e1cd42c46","ui_kits/app/LoginScreen.jsx":"1abf8f8e169c","ui_kits/app/PerfilScreen.jsx":"ec51f56200c8","ui_kits/app/data.js":"419a8c0413c7"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.ProyectosYaDesignSystem_1dd038 = window.ProyectosYaDesignSystem_1dd038 || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Icon.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
/**
 * Thin wrapper around Lucide icons. Requires the Lucide UMD script to be
 * loaded on the page (https://unpkg.com/lucide@latest). Renders an <i> that
 * Lucide hydrates into an inline SVG, so icons inherit `currentColor`.
 */
function Icon({
  name,
  size = 20,
  strokeWidth = 2,
  color = 'currentColor',
  style = {},
  ...rest
}) {
  const ref = React.useRef(null);
  React.useEffect(() => {
    const el = ref.current;
    if (!el || typeof window === 'undefined' || !window.lucide) return;
    el.innerHTML = '';
    const node = document.createElement('i');
    node.setAttribute('data-lucide', name);
    el.appendChild(node);
    try {
      window.lucide.createIcons({
        attrs: {
          width: size,
          height: size,
          'stroke-width': strokeWidth
        }
      });
    } catch (e) {}
  }, [name, size, strokeWidth]);
  return /*#__PURE__*/React.createElement("span", _extends({
    ref: ref,
    "aria-hidden": "true",
    style: {
      display: 'inline-flex',
      width: size,
      height: size,
      color,
      flex: 'none',
      ...style
    }
  }, rest));
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Icon.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Badge.jsx
try { (() => {
const TONES = {
  neutral: {
    bg: 'var(--warm-100)',
    fg: 'var(--warm-700)',
    bd: 'var(--warm-200)'
  },
  teal: {
    bg: 'var(--teal-50)',
    fg: 'var(--teal-700)',
    bd: 'var(--teal-200)'
  },
  coral: {
    bg: 'var(--coral-50)',
    fg: 'var(--coral-700)',
    bd: 'var(--coral-200)'
  },
  success: {
    bg: 'var(--success-soft)',
    fg: 'var(--green-600)',
    bd: 'transparent'
  },
  warning: {
    bg: 'var(--warning-soft)',
    fg: 'var(--amber-600)',
    bd: 'transparent'
  },
  danger: {
    bg: 'var(--danger-soft)',
    fg: 'var(--red-600)',
    bd: 'transparent'
  },
  info: {
    bg: 'var(--info-soft)',
    fg: 'var(--blue-500)',
    bd: 'transparent'
  },
  solid: {
    bg: 'var(--primary)',
    fg: 'var(--on-primary)',
    bd: 'transparent'
  }
};
function Badge({
  children,
  tone = 'neutral',
  dot = false,
  iconLeft = null,
  style = {}
}) {
  const t = TONES[tone] || TONES.neutral;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-xs)',
      fontWeight: 'var(--weight-semibold)',
      lineHeight: 1,
      letterSpacing: '0.01em',
      padding: '5px 10px',
      borderRadius: 'var(--radius-pill)',
      whiteSpace: 'nowrap',
      background: t.bg,
      color: t.fg,
      border: `1px solid ${t.bd}`,
      ...style
    }
  }, dot && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: '50%',
      background: 'currentColor'
    }
  }), iconLeft, children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Badge.jsx", error: String((e && e.message) || e) }); }

// components/feedback/MatchMeter.jsx
try { (() => {
/** Resolve the brand colour for a compatibility score. */
function scoreColor(v) {
  if (v >= 80) return 'var(--teal-500)';
  if (v >= 60) return 'var(--amber-500)';
  return 'var(--warm-400)';
}
const SIZES = {
  sm: {
    d: 44,
    stroke: 5,
    font: 13
  },
  md: {
    d: 64,
    stroke: 6,
    font: 18
  },
  lg: {
    d: 92,
    stroke: 8,
    font: 26
  }
};
function MatchMeter({
  value = 0,
  size = 'md',
  label,
  showValue = true,
  style = {}
}) {
  const s = SIZES[size] || SIZES.md;
  const v = Math.max(0, Math.min(100, Math.round(value)));
  const r = (s.d - s.stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = scoreColor(v);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: label ? 12 : 0,
      fontFamily: 'var(--font-sans)',
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      width: s.d,
      height: s.d,
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: s.d,
    height: s.d,
    viewBox: `0 0 ${s.d} ${s.d}`,
    style: {
      transform: 'rotate(-90deg)'
    }
  }, /*#__PURE__*/React.createElement("circle", {
    cx: s.d / 2,
    cy: s.d / 2,
    r: r,
    fill: "none",
    stroke: "var(--warm-200)",
    strokeWidth: s.stroke
  }), /*#__PURE__*/React.createElement("circle", {
    cx: s.d / 2,
    cy: s.d / 2,
    r: r,
    fill: "none",
    stroke: color,
    strokeWidth: s.stroke,
    strokeLinecap: "round",
    strokeDasharray: c,
    strokeDashoffset: c - c * v / 100,
    style: {
      transition: 'stroke-dashoffset var(--dur-slow) var(--ease-out)'
    }
  })), showValue && /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      inset: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      fontSize: s.font,
      color: 'var(--text-strong)'
    }
  }, v, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: '0.6em',
      marginLeft: 1,
      color: 'var(--text-subtle)'
    }
  }, "%"))), label && /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 2
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      fontWeight: 600,
      color: 'var(--text-subtle)'
    }
  }, "Compatibilidad"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-sm)',
      fontWeight: 600,
      color
    }
  }, label)));
}
Object.assign(__ds_scope, { MatchMeter });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/MatchMeter.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Tag.jsx
try { (() => {
function Tag({
  children,
  active = false,
  onRemove,
  onClick,
  iconLeft = null,
  style = {}
}) {
  const [hover, setHover] = React.useState(false);
  const clickable = onClick || onRemove;
  return /*#__PURE__*/React.createElement("span", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-sm)',
      fontWeight: 'var(--weight-medium)',
      padding: '6px 12px',
      borderRadius: 'var(--radius-pill)',
      whiteSpace: 'nowrap',
      background: active ? 'var(--primary-soft)' : hover && clickable ? 'var(--warm-100)' : 'var(--surface-card)',
      color: active ? 'var(--primary-active)' : 'var(--text-body)',
      border: `1px solid ${active ? 'var(--primary-border)' : 'var(--border-default)'}`,
      cursor: clickable ? 'pointer' : 'default',
      transition: 'background var(--dur-fast) var(--ease-standard)',
      ...style
    }
  }, iconLeft, children, onRemove && /*#__PURE__*/React.createElement("button", {
    type: "button",
    "aria-label": "Quitar",
    onClick: e => {
      e.stopPropagation();
      onRemove(e);
    },
    style: {
      display: 'inline-flex',
      border: 'none',
      background: 'transparent',
      padding: 0,
      marginRight: -2,
      cursor: 'pointer',
      color: 'inherit',
      opacity: 0.7
    }
  }, /*#__PURE__*/React.createElement("svg", {
    width: "14",
    height: "14",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2.4",
    strokeLinecap: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M18 6 6 18M6 6l12 12"
  }))));
}
Object.assign(__ds_scope, { Tag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Tag.jsx", error: String((e && e.message) || e) }); }

// components/forms/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: {
    fontSize: 'var(--text-sm)',
    padding: '7px 14px',
    height: 34,
    gap: 6,
    radius: 'var(--radius-sm)'
  },
  md: {
    fontSize: 'var(--text-base)',
    padding: '10px 18px',
    height: 42,
    gap: 8,
    radius: 'var(--radius-md)'
  },
  lg: {
    fontSize: 'var(--text-lg)',
    padding: '13px 24px',
    height: 52,
    gap: 10,
    radius: 'var(--radius-md)'
  }
};
const VARIANTS = {
  primary: {
    rest: {
      background: 'var(--primary)',
      color: 'var(--on-primary)',
      border: '1px solid transparent',
      boxShadow: 'var(--shadow-xs)'
    },
    hover: {
      background: 'var(--primary-hover)'
    },
    active: {
      background: 'var(--primary-active)'
    }
  },
  accent: {
    rest: {
      background: 'var(--accent)',
      color: 'var(--on-accent)',
      border: '1px solid transparent',
      boxShadow: 'var(--shadow-xs)'
    },
    hover: {
      background: 'var(--accent-hover)'
    },
    active: {
      background: 'var(--accent-active)'
    }
  },
  secondary: {
    rest: {
      background: 'var(--surface-card)',
      color: 'var(--text-strong)',
      border: '1px solid var(--border-default)',
      boxShadow: 'var(--shadow-xs)'
    },
    hover: {
      background: 'var(--warm-50)',
      border: '1px solid var(--border-strong)'
    },
    active: {
      background: 'var(--warm-100)'
    }
  },
  ghost: {
    rest: {
      background: 'transparent',
      color: 'var(--text-body)',
      border: '1px solid transparent'
    },
    hover: {
      background: 'var(--warm-100)'
    },
    active: {
      background: 'var(--warm-200)'
    }
  },
  soft: {
    rest: {
      background: 'var(--primary-soft)',
      color: 'var(--primary-active)',
      border: '1px solid transparent'
    },
    hover: {
      background: 'var(--teal-100)'
    },
    active: {
      background: 'var(--teal-200)'
    }
  }
};
function Button({
  children,
  variant = 'primary',
  size = 'md',
  iconLeft = null,
  iconRight = null,
  fullWidth = false,
  disabled = false,
  type = 'button',
  onClick,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [press, setPress] = React.useState(false);
  const s = SIZES[size] || SIZES.md;
  const v = VARIANTS[variant] || VARIANTS.primary;
  const composed = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: s.gap,
    fontFamily: 'var(--font-sans)',
    fontWeight: 'var(--weight-semibold)',
    fontSize: s.fontSize,
    lineHeight: 1,
    letterSpacing: '-0.005em',
    whiteSpace: 'nowrap',
    padding: s.padding,
    minHeight: s.height,
    borderRadius: s.radius,
    width: fullWidth ? '100%' : 'auto',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'background var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard)',
    transform: press && !disabled ? 'scale(0.97)' : 'scale(1)',
    opacity: disabled ? 0.5 : 1,
    ...v.rest,
    ...(hover && !disabled ? v.hover : null),
    ...(press && !disabled ? v.active : null),
    ...style
  };
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled,
    onClick: onClick,
    style: composed,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setPress(false);
    },
    onMouseDown: () => setPress(true),
    onMouseUp: () => setPress(false)
  }, rest), iconLeft, children, iconRight);
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Button.jsx", error: String((e && e.message) || e) }); }

// components/forms/Checkbox.jsx
try { (() => {
function Checkbox({
  checked = false,
  onChange,
  label,
  disabled = false,
  id,
  style = {}
}) {
  const autoId = React.useId();
  const fieldId = id || autoId;
  return /*#__PURE__*/React.createElement("label", {
    htmlFor: fieldId,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 10,
      cursor: disabled ? 'not-allowed' : 'pointer',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-base)',
      color: 'var(--text-body)',
      opacity: disabled ? 0.5 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("input", {
    id: fieldId,
    type: "checkbox",
    checked: checked,
    disabled: disabled,
    onChange: e => onChange && onChange(e.target.checked, e),
    style: {
      position: 'absolute',
      opacity: 0,
      width: 0,
      height: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 20,
      height: 20,
      borderRadius: 'var(--radius-xs)',
      flex: 'none',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: checked ? 'var(--primary)' : 'var(--surface-card)',
      border: `1.5px solid ${checked ? 'var(--primary)' : 'var(--border-strong)'}`,
      transition: 'background var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard)'
    }
  }, checked && /*#__PURE__*/React.createElement("svg", {
    width: "13",
    height: "13",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "var(--on-primary)",
    strokeWidth: "3.5",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }, /*#__PURE__*/React.createElement("path", {
    d: "M20 6 9 17l-5-5"
  }))), label && /*#__PURE__*/React.createElement("span", null, label));
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/forms/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: 34,
  md: 42,
  lg: 48
};
function IconButton({
  icon,
  label,
  variant = 'secondary',
  size = 'md',
  disabled = false,
  onClick,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [press, setPress] = React.useState(false);
  const dim = SIZES[size] || SIZES.md;
  const variants = {
    primary: {
      background: 'var(--primary)',
      color: 'var(--on-primary)',
      border: '1px solid transparent',
      hover: 'var(--primary-hover)'
    },
    secondary: {
      background: 'var(--surface-card)',
      color: 'var(--text-body)',
      border: '1px solid var(--border-default)',
      hover: 'var(--warm-50)'
    },
    ghost: {
      background: 'transparent',
      color: 'var(--text-muted)',
      border: '1px solid transparent',
      hover: 'var(--warm-100)'
    }
  };
  const v = variants[variant] || variants.secondary;
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    "aria-label": label,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => {
      setHover(false);
      setPress(false);
    },
    onMouseDown: () => setPress(true),
    onMouseUp: () => setPress(false),
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: dim,
      height: dim,
      borderRadius: 'var(--radius-md)',
      background: hover && !disabled ? v.hover : v.background,
      color: v.color,
      border: v.border,
      cursor: disabled ? 'not-allowed' : 'pointer',
      opacity: disabled ? 0.5 : 1,
      transform: press && !disabled ? 'scale(0.94)' : 'scale(1)',
      transition: 'background var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-standard)',
      ...style
    }
  }, rest), icon);
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Input({
  label,
  hint,
  error,
  iconLeft = null,
  value,
  onChange,
  placeholder,
  type = 'text',
  disabled = false,
  id,
  style = {},
  ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const autoId = React.useId();
  const fieldId = id || autoId;
  const borderColor = error ? 'var(--danger)' : focus ? 'var(--primary)' : 'var(--border-default)';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      fontFamily: 'var(--font-sans)',
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: fieldId,
    style: {
      fontSize: 'var(--text-sm)',
      fontWeight: 'var(--weight-medium)',
      color: 'var(--text-body)'
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      background: disabled ? 'var(--surface-inset)' : 'var(--surface-card)',
      border: `1px solid ${borderColor}`,
      borderRadius: 'var(--radius-md)',
      padding: '0 12px',
      height: 44,
      boxShadow: focus ? `0 0 0 3px ${error ? 'var(--ring-accent)' : 'var(--ring)'}` : 'none',
      transition: 'border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard)'
    }
  }, iconLeft && /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-subtle)',
      display: 'inline-flex'
    }
  }, iconLeft), /*#__PURE__*/React.createElement("input", _extends({
    id: fieldId,
    type: type,
    value: value,
    onChange: onChange,
    placeholder: placeholder,
    disabled: disabled,
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      flex: 1,
      border: 'none',
      outline: 'none',
      background: 'transparent',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-base)',
      color: 'var(--text-strong)',
      minWidth: 0
    }
  }, rest))), (hint || error) && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: error ? 'var(--danger)' : 'var(--text-subtle)'
    }
  }, error || hint));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function Select({
  label,
  hint,
  value,
  onChange,
  options = [],
  placeholder,
  disabled = false,
  id,
  style = {}
}) {
  const [focus, setFocus] = React.useState(false);
  const autoId = React.useId();
  const fieldId = id || autoId;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      fontFamily: 'var(--font-sans)',
      ...style
    }
  }, label && /*#__PURE__*/React.createElement("label", {
    htmlFor: fieldId,
    style: {
      fontSize: 'var(--text-sm)',
      fontWeight: 'var(--weight-medium)',
      color: 'var(--text-body)'
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative'
    }
  }, /*#__PURE__*/React.createElement("select", {
    id: fieldId,
    value: value,
    disabled: disabled,
    onChange: e => onChange && onChange(e.target.value, e),
    onFocus: () => setFocus(true),
    onBlur: () => setFocus(false),
    style: {
      width: '100%',
      appearance: 'none',
      WebkitAppearance: 'none',
      height: 44,
      padding: '0 40px 0 12px',
      borderRadius: 'var(--radius-md)',
      background: disabled ? 'var(--surface-inset)' : 'var(--surface-card)',
      border: `1px solid ${focus ? 'var(--primary)' : 'var(--border-default)'}`,
      boxShadow: focus ? '0 0 0 3px var(--ring)' : 'none',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-base)',
      color: value ? 'var(--text-strong)' : 'var(--text-subtle)',
      cursor: disabled ? 'not-allowed' : 'pointer',
      outline: 'none',
      transition: 'border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard)'
    }
  }, placeholder && /*#__PURE__*/React.createElement("option", {
    value: "",
    disabled: true,
    hidden: true
  }, placeholder), options.map(o => {
    const val = typeof o === 'string' ? o : o.value;
    const lab = typeof o === 'string' ? o : o.label;
    return /*#__PURE__*/React.createElement("option", {
      key: val,
      value: val
    }, lab);
  })), /*#__PURE__*/React.createElement("svg", {
    width: "18",
    height: "18",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "var(--text-subtle)",
    strokeWidth: "2.2",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    style: {
      position: 'absolute',
      right: 12,
      top: '50%',
      transform: 'translateY(-50%)',
      pointerEvents: 'none'
    }
  }, /*#__PURE__*/React.createElement("path", {
    d: "m6 9 6 6 6-6"
  }))), hint && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-subtle)'
    }
  }, hint));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/forms/Switch.jsx
try { (() => {
function Switch({
  checked = false,
  onChange,
  label,
  disabled = false,
  id,
  style = {}
}) {
  const autoId = React.useId();
  const fieldId = id || autoId;
  return /*#__PURE__*/React.createElement("label", {
    htmlFor: fieldId,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 10,
      cursor: disabled ? 'not-allowed' : 'pointer',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-base)',
      color: 'var(--text-body)',
      opacity: disabled ? 0.5 : 1,
      ...style
    }
  }, /*#__PURE__*/React.createElement("input", {
    id: fieldId,
    type: "checkbox",
    checked: checked,
    disabled: disabled,
    onChange: e => onChange && onChange(e.target.checked, e),
    style: {
      position: 'absolute',
      opacity: 0,
      width: 0,
      height: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 40,
      height: 24,
      borderRadius: 'var(--radius-pill)',
      flex: 'none',
      position: 'relative',
      background: checked ? 'var(--primary)' : 'var(--warm-300)',
      transition: 'background var(--dur-base) var(--ease-standard)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      position: 'absolute',
      top: 3,
      left: checked ? 19 : 3,
      width: 18,
      height: 18,
      borderRadius: '50%',
      background: 'var(--white)',
      boxShadow: 'var(--shadow-sm)',
      transition: 'left var(--dur-base) var(--ease-out)'
    }
  })), label && /*#__PURE__*/React.createElement("span", null, label));
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Switch.jsx", error: String((e && e.message) || e) }); }

// components/layout/Avatar.jsx
try { (() => {
const SIZES = {
  xs: 24,
  sm: 32,
  md: 40,
  lg: 56
};
const PALETTE = ['var(--teal-500)', 'var(--coral-500)', 'var(--teal-700)', 'var(--amber-500)', 'var(--blue-500)', 'var(--green-500)'];
function initials(name = '') {
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0] || '').join('').toUpperCase();
}
function Avatar({
  name = '',
  src,
  size = 'md',
  shape = 'circle',
  style = {}
}) {
  const dim = SIZES[size] || SIZES.md;
  const radius = shape === 'square' ? 'var(--radius-md)' : '50%';
  const idx = name ? name.charCodeAt(0) % PALETTE.length : 0;
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      width: dim,
      height: dim,
      borderRadius: radius,
      flex: 'none',
      overflow: 'hidden',
      background: src ? 'var(--warm-200)' : PALETTE[idx],
      color: 'var(--white)',
      fontFamily: 'var(--font-sans)',
      fontWeight: 'var(--weight-semibold)',
      fontSize: dim * 0.4,
      letterSpacing: '0.01em',
      userSelect: 'none',
      ...style
    }
  }, src ? /*#__PURE__*/React.createElement("img", {
    src: src,
    alt: name,
    style: {
      width: '100%',
      height: '100%',
      objectFit: 'cover'
    }
  }) : initials(name));
}
Object.assign(__ds_scope, { Avatar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/layout/Avatar.jsx", error: String((e && e.message) || e) }); }

// components/layout/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Card({
  children,
  padding = 20,
  interactive = false,
  elevation = 'sm',
  onClick,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const shadows = {
    none: 'none',
    xs: 'var(--shadow-xs)',
    sm: 'var(--shadow-sm)',
    md: 'var(--shadow-md)',
    lg: 'var(--shadow-lg)'
  };
  const base = shadows[elevation] ?? shadows.sm;
  return /*#__PURE__*/React.createElement("div", _extends({
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      background: 'var(--surface-card)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-lg)',
      padding,
      boxShadow: interactive && hover ? 'var(--shadow-md)' : base,
      transform: interactive && hover ? 'translateY(-2px)' : 'translateY(0)',
      cursor: interactive ? 'pointer' : 'default',
      transition: 'box-shadow var(--dur-base) var(--ease-standard), transform var(--dur-base) var(--ease-standard), border-color var(--dur-base) var(--ease-standard)',
      borderColor: interactive && hover ? 'var(--border-default)' : 'var(--border-subtle)',
      ...style
    }
  }, rest), children);
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/layout/Card.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
function Tabs({
  tabs = [],
  value,
  onChange,
  style = {}
}) {
  const items = tabs.map(t => typeof t === 'string' ? {
    value: t,
    label: t
  } : t);
  const active = value ?? items[0]?.value;
  return /*#__PURE__*/React.createElement("div", {
    role: "tablist",
    style: {
      display: 'flex',
      gap: 4,
      borderBottom: '1px solid var(--border-subtle)',
      fontFamily: 'var(--font-sans)',
      ...style
    }
  }, items.map(t => {
    const isActive = t.value === active;
    return /*#__PURE__*/React.createElement("button", {
      key: t.value,
      role: "tab",
      "aria-selected": isActive,
      onClick: () => onChange && onChange(t.value),
      style: {
        position: 'relative',
        border: 'none',
        background: 'transparent',
        cursor: 'pointer',
        padding: '10px 14px 12px',
        marginBottom: -1,
        fontFamily: 'var(--font-sans)',
        fontSize: 'var(--text-sm)',
        fontWeight: 'var(--weight-semibold)',
        color: isActive ? 'var(--text-strong)' : 'var(--text-muted)',
        display: 'inline-flex',
        alignItems: 'center',
        gap: 7,
        transition: 'color var(--dur-fast) var(--ease-standard)'
      }
    }, t.icon, t.label, t.count != null && /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: 'var(--font-mono)',
        fontSize: 11,
        padding: '1px 7px',
        borderRadius: 'var(--radius-pill)',
        background: isActive ? 'var(--primary-soft)' : 'var(--warm-100)',
        color: isActive ? 'var(--primary-active)' : 'var(--text-muted)'
      }
    }, t.count), /*#__PURE__*/React.createElement("span", {
      style: {
        position: 'absolute',
        left: 8,
        right: 8,
        bottom: 0,
        height: 2.5,
        borderRadius: '3px 3px 0 0',
        background: isActive ? 'var(--primary)' : 'transparent',
        transition: 'background var(--dur-fast) var(--ease-standard)'
      }
    }));
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// ui_kits/app/AppShell.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// AppShell — sidebar + topbar chrome for the ProyectosYa app.
const {
  Avatar,
  IconButton,
  Icon,
  Badge
} = window.DS;
function NavItem({
  icon,
  label,
  active,
  badge,
  onClick
}) {
  const [hover, setHover] = React.useState(false);
  return /*#__PURE__*/React.createElement("button", {
    onClick: onClick,
    onMouseEnter: () => setHover(true),
    onMouseLeave: () => setHover(false),
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      width: '100%',
      textAlign: 'left',
      padding: '10px 12px',
      borderRadius: 'var(--radius-md)',
      border: 'none',
      cursor: 'pointer',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-sm)',
      fontWeight: active ? 600 : 500,
      color: active ? 'var(--primary-active)' : 'var(--text-muted)',
      background: active ? 'var(--primary-soft)' : hover ? 'var(--warm-100)' : 'transparent',
      transition: 'background var(--dur-fast) var(--ease-standard)'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: icon,
    size: 20,
    color: active ? 'var(--primary)' : 'var(--text-subtle)'
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1
    }
  }, label), badge != null && /*#__PURE__*/React.createElement(Badge, {
    tone: active ? 'teal' : 'neutral'
  }, badge));
}
function AppShell({
  active,
  onNav,
  children,
  search,
  onSearch
}) {
  const u = window.PYDATA.user;
  const nav = [{
    key: 'dashboard',
    icon: 'sparkles',
    label: 'Para ti',
    badge: window.PYDATA.stats.nuevas
  }, {
    key: 'licitaciones',
    icon: 'search',
    label: 'Explorar'
  }, {
    key: 'guardadas',
    icon: 'bookmark',
    label: 'Guardadas',
    badge: window.PYDATA.stats.guardadas
  }, {
    key: 'postuladas',
    icon: 'send',
    label: 'Postuladas'
  }, {
    key: 'perfil',
    icon: 'building-2',
    label: 'Mi empresa'
  }];
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      minHeight: '100%',
      background: 'var(--bg-page)'
    }
  }, /*#__PURE__*/React.createElement("aside", {
    style: {
      width: 248,
      flex: 'none',
      background: 'var(--surface-card)',
      borderRight: '1px solid var(--border-subtle)',
      display: 'flex',
      flexDirection: 'column',
      padding: 16,
      gap: 4,
      position: 'sticky',
      top: 0,
      height: '100vh'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '6px 8px 16px'
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-wordmark.svg",
    alt: "ProyectosYa",
    style: {
      height: 30
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
      color: 'var(--text-subtle)',
      padding: '4px 12px'
    }
  }, "Oportunidades"), nav.map(n => /*#__PURE__*/React.createElement(NavItem, _extends({
    key: n.key
  }, n, {
    active: active === n.key,
    onClick: () => onNav(n.key)
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      borderTop: '1px solid var(--border-subtle)',
      paddingTop: 12,
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: u.name,
    size: "md"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 13,
      fontWeight: 600,
      color: 'var(--text-strong)',
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    }
  }, u.name), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      color: 'var(--text-subtle)',
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    }
  }, u.company)), /*#__PURE__*/React.createElement(IconButton, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "settings",
      size: 18
    }),
    label: "Configuraci\xF3n",
    variant: "ghost",
    size: "sm"
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("header", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      padding: '14px 28px',
      borderBottom: '1px solid var(--border-subtle)',
      background: 'color-mix(in srgb, var(--bg-page) 80%, transparent)',
      backdropFilter: 'blur(8px)',
      position: 'sticky',
      top: 0,
      zIndex: 5
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      flex: 1,
      maxWidth: 460,
      background: 'var(--surface-card)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--radius-md)',
      padding: '0 12px',
      height: 42
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "search",
    size: 18,
    color: "var(--text-subtle)"
  }), /*#__PURE__*/React.createElement("input", {
    value: search,
    onChange: e => onSearch && onSearch(e.target.value),
    placeholder: "Buscar por rubro, organismo o ID\u2026",
    style: {
      flex: 1,
      border: 'none',
      outline: 'none',
      background: 'transparent',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-sm)',
      color: 'var(--text-strong)'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(IconButton, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: "bell",
      size: 20
    }),
    label: "Alertas",
    variant: "secondary"
  }), /*#__PURE__*/React.createElement(Avatar, {
    name: u.name,
    size: "md"
  })), /*#__PURE__*/React.createElement("main", {
    style: {
      flex: 1,
      overflow: 'auto'
    }
  }, children)));
}
Object.assign(window, {
  AppShell
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/app/AppShell.jsx", error: String((e && e.message) || e) }); }

// ui_kits/app/DashboardScreen.jsx
try { (() => {
// DashboardScreen — "Para ti" matched-tender feed.
const {
  Card,
  Tabs,
  Tag,
  Select,
  MatchMeter,
  Icon,
  Button
} = window.DS;
function StatTile({
  icon,
  value,
  label,
  tone
}) {
  return /*#__PURE__*/React.createElement(Card, {
    padding: 16,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 40,
      height: 40,
      borderRadius: 'var(--radius-md)',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: tone.bg,
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: icon,
    size: 20,
    color: tone.fg
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-display)',
      fontWeight: 700,
      fontSize: 'var(--text-2xl)',
      color: 'var(--text-strong)',
      lineHeight: 1
    }
  }, value), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)'
    }
  }, label)));
}
function DashboardScreen({
  onOpen,
  saved,
  onToggleSave
}) {
  const D = window.PYDATA;
  const [tab, setTab] = React.useState('match');
  const [rubro, setRubro] = React.useState('Todos');
  const list = D.licitaciones;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '28px 28px 48px',
      maxWidth: 920,
      margin: '0 auto'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      marginBottom: 20
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "eyebrow",
    style: {
      marginBottom: 6
    }
  }, "Lunes 9 de junio"), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontSize: 'var(--text-4xl)',
      margin: '0 0 6px'
    }
  }, "Hola, ", D.user.name.split(' ')[0]), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 'var(--text-lg)',
      color: 'var(--text-muted)',
      margin: 0
    }
  }, "Encontramos ", /*#__PURE__*/React.createElement("strong", {
    style: {
      color: 'var(--text-strong)'
    }
  }, D.stats.nuevas, " licitaciones nuevas"), " que calzan con tu perfil esta semana.")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
      gap: 14,
      marginBottom: 24
    }
  }, /*#__PURE__*/React.createElement(StatTile, {
    icon: "sparkles",
    value: D.stats.nuevas,
    label: "Nuevas para ti",
    tone: {
      bg: 'var(--teal-50)',
      fg: 'var(--teal-600)'
    }
  }), /*#__PURE__*/React.createElement(StatTile, {
    icon: "send",
    value: D.stats.postuladas,
    label: "Postuladas",
    tone: {
      bg: 'var(--coral-50)',
      fg: 'var(--coral-600)'
    }
  }), /*#__PURE__*/React.createElement(StatTile, {
    icon: "bookmark",
    value: D.stats.guardadas,
    label: "Guardadas",
    tone: {
      bg: 'var(--warm-100)',
      fg: 'var(--text-muted)'
    }
  }), /*#__PURE__*/React.createElement(StatTile, {
    icon: "trophy",
    value: D.stats.adjudicadas,
    label: "Adjudicadas",
    tone: {
      bg: 'var(--success-soft)',
      fg: 'var(--green-600)'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end',
      justifyContent: 'space-between',
      gap: 16,
      marginBottom: 16,
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement(Tabs, {
    value: tab,
    onChange: setTab,
    tabs: [{
      value: 'match',
      label: 'Para ti',
      count: D.stats.nuevas
    }, {
      value: 'todas',
      label: 'Todas',
      count: 142
    }, {
      value: 'cierran',
      label: 'Cierran pronto'
    }]
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 10,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(Select, {
    value: rubro,
    onChange: setRubro,
    options: ['Todos', ...D.rubros],
    style: {
      width: 200
    }
  }))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 14
    }
  }, list.map(lic => /*#__PURE__*/React.createElement(window.LicitacionCard, {
    key: lic.id,
    lic: lic,
    onOpen: onOpen,
    saved: saved.includes(lic.id),
    onToggleSave: onToggleSave
  }))));
}
Object.assign(window, {
  DashboardScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/app/DashboardScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/app/LicitacionCard.jsx
try { (() => {
// LicitacionCard — feed row for a tender. Used in the dashboard.
const {
  Card,
  Badge,
  Tag,
  Button,
  MatchMeter,
  IconButton,
  Icon
} = window.DS;
function deadlineTone(d) {
  return d <= 3 ? 'warning' : d <= 7 ? 'neutral' : 'neutral';
}
function LicitacionCard({
  lic,
  onOpen,
  saved,
  onToggleSave
}) {
  return /*#__PURE__*/React.createElement(Card, {
    interactive: true,
    padding: 20,
    onClick: () => onOpen(lic),
    style: {
      display: 'flex',
      gap: 18,
      alignItems: 'flex-start'
    }
  }, /*#__PURE__*/React.createElement(MatchMeter, {
    value: lic.match,
    size: "lg"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      alignItems: 'center',
      marginBottom: 8,
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "teal"
  }, "Compra \xC1gil"), /*#__PURE__*/React.createElement(Badge, {
    tone: deadlineTone(lic.cierra),
    dot: lic.cierra <= 3
  }, lic.cierra <= 3 ? `Cierra en ${lic.cierra} días` : `Cierra en ${lic.cierra} días`), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      color: 'var(--text-subtle)'
    }
  }, "ID ", lic.id)), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-display)',
      fontWeight: 600,
      fontSize: 'var(--text-xl)',
      color: 'var(--text-strong)',
      lineHeight: 1.2,
      letterSpacing: '-0.01em'
    }
  }, lic.title), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 6,
      marginTop: 6,
      color: 'var(--text-muted)',
      fontSize: 'var(--text-sm)'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "building-2",
    size: 15,
    color: "var(--text-subtle)"
  }), /*#__PURE__*/React.createElement("span", null, lic.organismo), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--border-strong)'
    }
  }, "\xB7"), /*#__PURE__*/React.createElement(Icon, {
    name: "map-pin",
    size: 15,
    color: "var(--text-subtle)"
  }), /*#__PURE__*/React.createElement("span", null, lic.region)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      marginTop: 14,
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      color: 'var(--text-subtle)',
      textTransform: 'uppercase',
      letterSpacing: '0.05em'
    }
  }, "Monto estimado"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      fontSize: 'var(--text-lg)',
      color: 'var(--text-strong)'
    }
  }, "$", lic.monto)), /*#__PURE__*/React.createElement(Tag, null, lic.rubro), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(IconButton, {
    icon: /*#__PURE__*/React.createElement(Icon, {
      name: saved ? 'bookmark-check' : 'bookmark',
      size: 18
    }),
    label: "Guardar",
    variant: saved ? 'primary' : 'secondary',
    onClick: e => {
      e.stopPropagation();
      onToggleSave(lic.id);
    }
  }), /*#__PURE__*/React.createElement(Button, {
    variant: "soft",
    iconRight: /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-right",
      size: 16
    }),
    onClick: e => {
      e.stopPropagation();
      onOpen(lic);
    }
  }, "Ver an\xE1lisis"))));
}
Object.assign(window, {
  LicitacionCard
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/app/LicitacionCard.jsx", error: String((e && e.message) || e) }); }

// ui_kits/app/LicitacionDetailScreen.jsx
try { (() => {
// LicitacionDetailScreen — full tender view with AI compatibility analysis.
const {
  Card,
  Badge,
  Tag,
  Button,
  MatchMeter,
  Icon,
  IconButton
} = window.DS;
function AnalysisRow({
  item,
  kind
}) {
  const good = kind === 'fuerte';
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 12,
      alignItems: 'flex-start',
      padding: '12px 0',
      borderBottom: '1px solid var(--border-subtle)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 28,
      height: 28,
      borderRadius: '50%',
      flex: 'none',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: good ? 'var(--success-soft)' : 'var(--warning-soft)'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: good ? 'check' : 'alert-triangle',
    size: 16,
    color: good ? 'var(--green-600)' : 'var(--amber-600)'
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 600,
      fontSize: 'var(--text-sm)',
      color: 'var(--text-strong)'
    }
  }, item.t), good && item.v != null && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      fontWeight: 600,
      color: 'var(--teal-600)'
    }
  }, item.v, "%")), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)',
      marginTop: 2
    }
  }, item.d)));
}
function DetailScreen({
  lic,
  onBack,
  saved,
  onToggleSave
}) {
  const a = lic.analisis;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '24px 28px 56px',
      maxWidth: 960,
      margin: '0 auto'
    }
  }, /*#__PURE__*/React.createElement("button", {
    onClick: onBack,
    style: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      border: 'none',
      background: 'transparent',
      cursor: 'pointer',
      color: 'var(--text-muted)',
      fontFamily: 'var(--font-sans)',
      fontSize: 'var(--text-sm)',
      fontWeight: 600,
      padding: '4px 0',
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "arrow-left",
    size: 16
  }), " Volver a oportunidades"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 8,
      alignItems: 'center',
      marginBottom: 12,
      flexWrap: 'wrap'
    }
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "teal"
  }, "Compra \xC1gil"), /*#__PURE__*/React.createElement(Badge, {
    tone: "warning",
    dot: true
  }, "Cierra en ", lic.cierra, " d\xEDas"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 13,
      color: 'var(--text-subtle)'
    }
  }, "ID ", lic.id)), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontSize: 'var(--text-3xl)',
      margin: '0 0 10px',
      maxWidth: 720
    }
  }, lic.title), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      color: 'var(--text-muted)',
      fontSize: 'var(--text-base)',
      marginBottom: 24
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "building-2",
    size: 17,
    color: "var(--text-subtle)"
  }), /*#__PURE__*/React.createElement("span", null, lic.organismo), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--border-strong)'
    }
  }, "\xB7"), /*#__PURE__*/React.createElement(Icon, {
    name: "map-pin",
    size: 17,
    color: "var(--text-subtle)"
  }), /*#__PURE__*/React.createElement("span", null, lic.region)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 320px',
      gap: 24,
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 20
    }
  }, /*#__PURE__*/React.createElement(Card, {
    padding: 22,
    style: {
      borderColor: 'var(--teal-200)',
      background: 'linear-gradient(180deg, var(--teal-50), var(--surface-card) 64%)'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 10,
      marginBottom: 4
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 34,
      height: 34,
      borderRadius: 'var(--radius-md)',
      background: 'var(--primary)',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      flex: 'none'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "sparkles",
    size: 19,
    color: "#fff"
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-display)',
      fontWeight: 600,
      fontSize: 'var(--text-lg)',
      color: 'var(--text-strong)'
    }
  }, "An\xE1lisis de compatibilidad"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)'
    }
  }, "Cruzamos esta licitaci\xF3n con tu perfil de empresa."))), a.fuerte.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 700,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
      color: 'var(--green-600)',
      marginTop: 16
    }
  }, "Por qu\xE9 calza contigo"), a.fuerte.map((it, i) => /*#__PURE__*/React.createElement(AnalysisRow, {
    key: i,
    item: it,
    kind: "fuerte"
  })), a.brechas.length > 0 && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 12,
      fontWeight: 700,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
      color: 'var(--amber-600)',
      marginTop: 16
    }
  }, "Brechas a cubrir"), a.brechas.map((it, i) => /*#__PURE__*/React.createElement(AnalysisRow, {
    key: i,
    item: it,
    kind: "brecha"
  }))), /*#__PURE__*/React.createElement(Card, {
    padding: 22
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 'var(--text-lg)',
      margin: '0 0 8px'
    }
  }, "Descripci\xF3n"), /*#__PURE__*/React.createElement("p", {
    style: {
      color: 'var(--text-body)',
      margin: 0,
      lineHeight: 1.6
    }
  }, lic.descripcion), /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 'var(--text-lg)',
      margin: '20px 0 10px'
    }
  }, "Requisitos"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 8
    }
  }, lic.requisitos.map((r, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    style: {
      display: 'flex',
      gap: 10,
      alignItems: 'flex-start'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "check-circle-2",
    size: 18,
    color: "var(--teal-500)",
    style: {
      marginTop: 1
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-body)',
      fontSize: 'var(--text-base)'
    }
  }, r)))))), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'sticky',
      top: 88,
      display: 'flex',
      flexDirection: 'column',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Card, {
    padding: 22,
    style: {
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement(MatchMeter, {
    value: lic.match,
    size: "lg",
    style: {
      justifyContent: 'center',
      marginBottom: 4
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      color: 'var(--teal-600)',
      marginTop: 8
    }
  }, "Compatibilidad ", lic.level.toLowerCase()), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)',
      marginBottom: 16
    }
  }, "Buenas opciones de adjudicaci\xF3n."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      padding: '12px 0',
      borderTop: '1px solid var(--border-subtle)',
      borderBottom: '1px solid var(--border-subtle)'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-muted)',
      fontSize: 'var(--text-sm)'
    }
  }, "Monto estimado"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      color: 'var(--text-strong)'
    }
  }, "$", lic.monto)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      padding: '12px 0',
      borderBottom: '1px solid var(--border-subtle)',
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--text-muted)',
      fontSize: 'var(--text-sm)'
    }
  }, "Cierra"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 600,
      color: 'var(--amber-600)'
    }
  }, "en ", lic.cierra, " d\xEDas")), /*#__PURE__*/React.createElement(Button, {
    variant: "accent",
    size: "lg",
    fullWidth: true,
    iconRight: /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-right",
      size: 18
    })
  }, "Postular ahora"), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    fullWidth: true,
    style: {
      marginTop: 10
    },
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      name: saved ? 'bookmark-check' : 'bookmark',
      size: 18
    }),
    onClick: () => onToggleSave(lic.id)
  }, saved ? 'Guardada' : 'Guardar')))));
}
Object.assign(window, {
  DetailScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/app/LicitacionDetailScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/app/LoginScreen.jsx
try { (() => {
// LoginScreen — split-panel sign in for the ProyectosYa app.
const {
  Button,
  Input,
  Checkbox,
  Badge,
  Card,
  MatchMeter,
  Avatar,
  Icon
} = window.DS;
function BrandPanel() {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      overflow: 'hidden',
      background: 'var(--teal-600)',
      padding: '48px 52px',
      display: 'flex',
      flexDirection: 'column',
      minHeight: '100%'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      right: -90,
      top: -90,
      width: 320,
      height: 320,
      borderRadius: '50%',
      background: 'var(--teal-500)',
      opacity: 0.45
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'absolute',
      right: 60,
      bottom: -120,
      width: 260,
      height: 260,
      borderRadius: '50%',
      background: 'var(--teal-700)',
      opacity: 0.5
    }
  }), /*#__PURE__*/React.createElement("img", {
    src: "../../assets/logo-wordmark-onteal.svg",
    alt: "ProyectosYa",
    style: {
      height: 32,
      position: 'relative',
      zIndex: 2
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      position: 'relative',
      zIndex: 2,
      marginTop: 'auto'
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      color: 'var(--warm-50)',
      fontSize: 'var(--text-5xl)',
      lineHeight: 1.05,
      letterSpacing: '-0.02em',
      margin: '0 0 16px',
      maxWidth: 420
    }
  }, "Postula a la licitaci\xF3n ", /*#__PURE__*/React.createElement("span", {
    style: {
      color: 'var(--coral-300)'
    }
  }, "correcta"), ", hoy."), /*#__PURE__*/React.createElement("p", {
    style: {
      color: 'var(--teal-100)',
      fontSize: 'var(--text-lg)',
      margin: '0 0 32px',
      maxWidth: 380
    }
  }, "Tus oportunidades de Compra \xC1gil, filtradas por IA y ordenadas por compatibilidad."), /*#__PURE__*/React.createElement(Card, {
    padding: 16,
    elevation: "lg",
    style: {
      maxWidth: 360,
      display: 'flex',
      gap: 14,
      alignItems: 'center'
    }
  }, /*#__PURE__*/React.createElement(MatchMeter, {
    value: 94,
    size: "md"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement(Badge, {
    tone: "teal",
    style: {
      marginBottom: 6
    }
  }, "Nuevo match"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-display)',
      fontWeight: 600,
      fontSize: 'var(--text-base)',
      color: 'var(--text-strong)',
      lineHeight: 1.2,
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis'
    }
  }, "Aseo y mantenci\xF3n municipal"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)'
    }
  }, "Municipalidad de \xD1u\xF1oa")))));
}
function LoginScreen({
  onSubmit
}) {
  const [usuario, setUsuario] = React.useState('');
  const [pass, setPass] = React.useState('');
  const [show, setShow] = React.useState(false);
  const [remember, setRemember] = React.useState(true);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      minHeight: '100vh',
      display: 'grid',
      gridTemplateColumns: '1.05fr 1fr',
      background: 'var(--bg-page)'
    }
  }, /*#__PURE__*/React.createElement(BrandPanel, null), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '40px'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: '100%',
      maxWidth: 380
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "eyebrow",
    style: {
      marginBottom: 8
    }
  }, "Bienvenido de vuelta"), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontSize: 'var(--text-4xl)',
      margin: '0 0 8px'
    }
  }, "Inicia sesi\xF3n"), /*#__PURE__*/React.createElement("p", {
    style: {
      color: 'var(--text-muted)',
      margin: '0 0 28px'
    }
  }, "Entra para ver tus licitaciones compatibles de hoy."), /*#__PURE__*/React.createElement("form", {
    onSubmit: e => {
      e.preventDefault();
      onSubmit && onSubmit();
    },
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 18
    }
  }, /*#__PURE__*/React.createElement(Input, {
    label: "RUT o correo",
    placeholder: "76.842.193-4",
    value: usuario,
    onChange: e => setUsuario(e.target.value),
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      name: "user",
      size: 18
    })
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Input, {
    label: "Contrase\xF1a",
    placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022",
    type: show ? 'text' : 'password',
    value: pass,
    onChange: e => setPass(e.target.value),
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      name: "lock",
      size: 18
    })
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginTop: 10
    }
  }, /*#__PURE__*/React.createElement(Checkbox, {
    checked: remember,
    onChange: setRemember,
    label: "Recordarme"
  }), /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      fontSize: 'var(--text-sm)',
      fontWeight: 600
    }
  }, "\xBFOlvidaste tu contrase\xF1a?"))), /*#__PURE__*/React.createElement(Button, {
    type: "submit",
    variant: "primary",
    size: "lg",
    fullWidth: true,
    iconRight: /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-right",
      size: 18
    })
  }, "Iniciar sesi\xF3n")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      margin: '22px 0'
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      height: 1,
      background: 'var(--border-subtle)'
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-xs)',
      color: 'var(--text-subtle)',
      textTransform: 'uppercase',
      letterSpacing: '0.06em'
    }
  }, "o contin\xFAa con"), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      height: 1,
      background: 'var(--border-subtle)'
    }
  })), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "lg",
    fullWidth: true,
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      name: "shield-check",
      size: 18
    })
  }, "Clave\xDAnica"), /*#__PURE__*/React.createElement("p", {
    style: {
      textAlign: 'center',
      color: 'var(--text-muted)',
      fontSize: 'var(--text-sm)',
      marginTop: 28
    }
  }, "\xBFNo tienes cuenta? ", /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      fontWeight: 600
    }
  }, "Crea tu perfil gratis")))));
}
Object.assign(window, {
  LoginScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/app/LoginScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/app/PerfilScreen.jsx
try { (() => {
// PerfilScreen — "Perfil inteligente" de la empresa.
const {
  Card,
  Badge,
  Tag,
  Button,
  Input,
  Select,
  MatchMeter,
  Avatar,
  Icon,
  Switch
} = window.DS;
function Field({
  label,
  value
}) {
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 11,
      fontWeight: 600,
      letterSpacing: '0.05em',
      textTransform: 'uppercase',
      color: 'var(--text-subtle)',
      marginBottom: 4
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 'var(--text-base)',
      color: 'var(--text-strong)',
      fontWeight: 500
    }
  }, value));
}
function PerfilScreen() {
  const D = window.PYDATA;
  const [alertas, setAlertas] = React.useState(true);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      padding: '28px 28px 56px',
      maxWidth: 920,
      margin: '0 auto'
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      fontSize: 'var(--text-4xl)',
      margin: '0 0 4px'
    }
  }, "Mi empresa"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 'var(--text-lg)',
      color: 'var(--text-muted)',
      margin: '0 0 24px'
    }
  }, "Mientras m\xE1s completo tu perfil, mejores ser\xE1n tus matches."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 300px',
      gap: 24,
      alignItems: 'start'
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 20
    }
  }, /*#__PURE__*/React.createElement(Card, {
    padding: 22
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 16,
      marginBottom: 20
    }
  }, /*#__PURE__*/React.createElement(Avatar, {
    name: D.user.company,
    shape: "square",
    size: "lg"
  }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-display)',
      fontWeight: 600,
      fontSize: 'var(--text-xl)',
      color: 'var(--text-strong)'
    }
  }, D.user.company), /*#__PURE__*/React.createElement("div", {
    style: {
      color: 'var(--text-muted)',
      fontSize: 'var(--text-sm)'
    }
  }, "RUT 76.842.193-4 \xB7 Peque\xF1a empresa")), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      name: "pencil",
      size: 16
    })
  }, "Editar")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 1fr',
      gap: 18,
      paddingTop: 18,
      borderTop: '1px solid var(--border-subtle)'
    }
  }, /*#__PURE__*/React.createElement(Field, {
    label: "Regi\xF3n",
    value: "Metropolitana"
  }), /*#__PURE__*/React.createElement(Field, {
    label: "Comuna",
    value: "Maip\xFA"
  }), /*#__PURE__*/React.createElement(Field, {
    label: "Actividad",
    value: "Servicios de aseo"
  }), /*#__PURE__*/React.createElement(Field, {
    label: "Inicio actividades",
    value: "Marzo 2019"
  }), /*#__PURE__*/React.createElement(Field, {
    label: "Tama\xF1o",
    value: "14 trabajadores"
  }), /*#__PURE__*/React.createElement(Field, {
    label: "Estado SII",
    value: "Al d\xEDa"
  }))), /*#__PURE__*/React.createElement(Card, {
    padding: 22
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 'var(--text-lg)',
      margin: 0
    }
  }, "Rubros y servicios"), /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-subtle)'
    }
  }, "Usados para el matching")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: 8
    }
  }, D.rubros.map(r => /*#__PURE__*/React.createElement(Tag, {
    key: r,
    active: true,
    onRemove: () => {}
  }, r)), /*#__PURE__*/React.createElement(Tag, {
    iconLeft: /*#__PURE__*/React.createElement(Icon, {
      name: "plus",
      size: 15
    })
  }, "Agregar rubro"))), /*#__PURE__*/React.createElement(Card, {
    padding: 22
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontSize: 'var(--text-lg)',
      margin: '0 0 14px'
    }
  }, "Documentos"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 10
    }
  }, [['Certificado de inicio de actividades', true], ['Boletín comercial', true], ['Certificado de manejo de residuos', false]].map(([doc, ok]) => /*#__PURE__*/React.createElement("div", {
    key: doc,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: 12,
      padding: '12px 14px',
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-md)',
      background: 'var(--bg-page)'
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: ok ? 'file-check-2' : 'file-plus',
    size: 20,
    color: ok ? 'var(--teal-600)' : 'var(--text-subtle)'
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      flex: 1,
      fontSize: 'var(--text-sm)',
      color: 'var(--text-body)',
      fontWeight: 500
    }
  }, doc), ok ? /*#__PURE__*/React.createElement(Badge, {
    tone: "success",
    dot: true
  }, "Cargado") : /*#__PURE__*/React.createElement(Button, {
    variant: "soft",
    size: "sm"
  }, "Subir")))))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      position: 'sticky',
      top: 88
    }
  }, /*#__PURE__*/React.createElement(Card, {
    padding: 22,
    style: {
      textAlign: 'center'
    }
  }, /*#__PURE__*/React.createElement(MatchMeter, {
    value: D.profileStrength,
    size: "lg",
    style: {
      justifyContent: 'center'
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-display)',
      fontWeight: 600,
      fontSize: 'var(--text-lg)',
      color: 'var(--text-strong)',
      marginTop: 10
    }
  }, "Fuerza del perfil"), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)',
      margin: '4px 0 16px'
    }
  }, "Completa 1 documento para llegar a 100%."), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    fullWidth: true,
    iconRight: /*#__PURE__*/React.createElement(Icon, {
      name: "arrow-right",
      size: 16
    })
  }, "Completar perfil")), /*#__PURE__*/React.createElement(Card, {
    padding: 20
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-start',
      gap: 10,
      marginBottom: 10
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "bell",
    size: 20,
    color: "var(--coral-500)"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      fontWeight: 600,
      color: 'var(--text-strong)'
    }
  }, "Alertas inteligentes")), /*#__PURE__*/React.createElement("p", {
    style: {
      fontSize: 'var(--text-sm)',
      color: 'var(--text-muted)',
      margin: '0 0 14px'
    }
  }, "Te avisamos por correo cuando aparezca una licitaci\xF3n con alta compatibilidad."), /*#__PURE__*/React.createElement(Switch, {
    checked: alertas,
    onChange: setAlertas,
    label: "Activadas"
  })))));
}
Object.assign(window, {
  PerfilScreen
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/app/PerfilScreen.jsx", error: String((e && e.message) || e) }); }

// ui_kits/app/data.js
try { (() => {
// Mock data for the ProyectosYa app UI kit. Fictional Compra Ágil tenders.
window.PYDATA = {
  user: {
    name: 'Camila Soto',
    company: 'Aseo Integral SpA',
    role: 'Representante legal'
  },
  profileStrength: 82,
  stats: {
    nuevas: 8,
    postuladas: 5,
    guardadas: 12,
    adjudicadas: 3
  },
  rubros: ['Servicios de aseo', 'Mantención', 'Jardinería', 'Control de plagas'],
  licitaciones: [{
    id: '4982-117-LE25',
    match: 94,
    level: 'Alta',
    title: 'Servicios de aseo y mantención de recintos municipales',
    organismo: 'Municipalidad de Ñuñoa',
    region: 'Región Metropolitana',
    monto: '12.480.000',
    cierra: 3,
    status: 'abierta',
    rubro: 'Servicios de aseo',
    publicada: 'Hace 2 días',
    descripcion: 'Se requiere la contratación de servicios de aseo integral y mantención para tres recintos municipales, incluyendo personal, insumos y maquinaria, por un período de 12 meses renovables.',
    requisitos: ['Experiencia mínima 2 años en servicios similares', 'Personal con contrato vigente', 'Certificación de manejo de residuos', 'Inicio de actividades en SII'],
    analisis: {
      fuerte: [{
        t: 'Rubro exacto',
        d: 'Tu giro principal coincide con el objeto de la licitación.',
        v: 98
      }, {
        t: 'Experiencia comprobable',
        d: '4 contratos similares en tu historial.',
        v: 92
      }, {
        t: 'Cobertura geográfica',
        d: 'Operas en la Región Metropolitana.',
        v: 95
      }],
      brechas: [{
        t: 'Certificación de residuos',
        d: 'Adjunta tu certificado vigente para reforzar la postulación.'
      }]
    }
  }, {
    id: '5103-204-LP25',
    match: 88,
    level: 'Alta',
    title: 'Mantención de áreas verdes y poda de árboles',
    organismo: 'Servicio de Vivienda y Urbanización RM',
    region: 'Región Metropolitana',
    monto: '8.900.000',
    cierra: 5,
    status: 'abierta',
    rubro: 'Jardinería',
    publicada: 'Hace 1 día',
    descripcion: 'Mantención periódica de áreas verdes, poda y retiro de ramas en conjuntos habitacionales.',
    requisitos: ['Cuadrilla con herramientas propias', 'Seguro de responsabilidad civil'],
    analisis: {
      fuerte: [{
        t: 'Rubro relacionado',
        d: 'Jardinería está en tus rubros declarados.',
        v: 88
      }],
      brechas: []
    }
  }, {
    id: '4771-330-CM25',
    match: 72,
    level: 'Media',
    title: 'Control de plagas en establecimientos educacionales',
    organismo: 'Corporación Municipal de Maipú',
    region: 'Región Metropolitana',
    monto: '5.200.000',
    cierra: 8,
    status: 'abierta',
    rubro: 'Control de plagas',
    publicada: 'Hace 3 días',
    descripcion: 'Servicio de desratización y desinsectación en 12 establecimientos educacionales.',
    requisitos: ['Resolución sanitaria vigente', 'Aplicadores certificados'],
    analisis: {
      fuerte: [{
        t: 'Rubro declarado',
        d: 'Control de plagas figura en tu perfil.',
        v: 80
      }],
      brechas: [{
        t: 'Resolución sanitaria',
        d: 'No tenemos registro de tu resolución vigente.'
      }]
    }
  }, {
    id: '3920-088-LE25',
    match: 58,
    level: 'Baja',
    title: 'Suministro de insumos de limpieza',
    organismo: 'Hospital Sótero del Río',
    region: 'Región Metropolitana',
    monto: '3.100.000',
    cierra: 11,
    status: 'abierta',
    rubro: 'Suministro',
    publicada: 'Hace 4 días',
    descripcion: 'Compra de insumos de limpieza e higiene para servicios clínicos.',
    requisitos: ['Distribuidor autorizado'],
    analisis: {
      fuerte: [],
      brechas: [{
        t: 'Giro de suministro',
        d: 'Tu empresa presta servicios, no suministra productos.'
      }]
    }
  }]
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/app/data.js", error: String((e && e.message) || e) }); }

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.MatchMeter = __ds_scope.MatchMeter;

__ds_ns.Tag = __ds_scope.Tag;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.Avatar = __ds_scope.Avatar;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Tabs = __ds_scope.Tabs;

})();
