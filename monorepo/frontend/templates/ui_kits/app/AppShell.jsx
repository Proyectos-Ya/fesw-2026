// AppShell — sidebar + topbar chrome for the ProyectosYa app.
const { Avatar, IconButton, Icon, Badge } = window.DS;

function NavItem({ icon, label, active, badge, onClick }) {
  const [hover, setHover] = React.useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 12, width: '100%', textAlign: 'left',
        padding: '10px 12px', borderRadius: 'var(--radius-md)', border: 'none', cursor: 'pointer',
        fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)', fontWeight: active ? 600 : 500,
        color: active ? 'var(--primary-active)' : 'var(--text-muted)',
        background: active ? 'var(--primary-soft)' : (hover ? 'var(--warm-100)' : 'transparent'),
        transition: 'background var(--dur-fast) var(--ease-standard)',
      }}>
      <Icon name={icon} size={20} color={active ? 'var(--primary)' : 'var(--text-subtle)'} />
      <span style={{ flex: 1 }}>{label}</span>
      {badge != null && <Badge tone={active ? 'teal' : 'neutral'}>{badge}</Badge>}
    </button>
  );
}

function AppShell({ active, onNav, children, search, onSearch }) {
  const u = window.PYDATA.user;
  const nav = [
    { key: 'dashboard', icon: 'sparkles', label: 'Para ti', badge: window.PYDATA.stats.nuevas },
    { key: 'licitaciones', icon: 'search', label: 'Explorar' },
    { key: 'guardadas', icon: 'bookmark', label: 'Guardadas', badge: window.PYDATA.stats.guardadas },
    { key: 'postuladas', icon: 'send', label: 'Postuladas' },
    { key: 'perfil', icon: 'building-2', label: 'Mi empresa' },
  ];
  return (
    <div style={{ display: 'flex', minHeight: '100%', background: 'var(--bg-page)' }}>
      {/* Sidebar */}
      <aside style={{
        width: 248, flex: 'none', background: 'var(--surface-card)', borderRight: '1px solid var(--border-subtle)',
        display: 'flex', flexDirection: 'column', padding: 16, gap: 4, position: 'sticky', top: 0, height: '100vh',
      }}>
        <div style={{ padding: '6px 8px 16px' }}>
          <img src="../../assets/logo-wordmark.svg" alt="ProyectosYa" style={{ height: 30 }} />
        </div>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--text-subtle)', padding: '4px 12px' }}>Oportunidades</div>
        {nav.map((n) => <NavItem key={n.key} {...n} active={active === n.key} onClick={() => onNav(n.key)} />)}
        <div style={{ flex: 1 }} />
        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
          <Avatar name={u.name} size="md" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-strong)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u.name}</div>
            <div style={{ fontSize: 12, color: 'var(--text-subtle)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{u.company}</div>
          </div>
          <IconButton icon={<Icon name="settings" size={18} />} label="Configuración" variant="ghost" size="sm" />
        </div>
      </aside>

      {/* Main column */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <header style={{
          display: 'flex', alignItems: 'center', gap: 16, padding: '14px 28px',
          borderBottom: '1px solid var(--border-subtle)', background: 'color-mix(in srgb, var(--bg-page) 80%, transparent)',
          backdropFilter: 'blur(8px)', position: 'sticky', top: 0, zIndex: 5,
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, flex: 1, maxWidth: 460,
            background: 'var(--surface-card)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)', padding: '0 12px', height: 42,
          }}>
            <Icon name="search" size={18} color="var(--text-subtle)" />
            <input value={search} onChange={(e) => onSearch && onSearch(e.target.value)} placeholder="Buscar por rubro, organismo o ID…"
              style={{ flex: 1, border: 'none', outline: 'none', background: 'transparent', fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)', color: 'var(--text-strong)' }} />
          </div>
          <div style={{ flex: 1 }} />
          <IconButton icon={<Icon name="bell" size={20} />} label="Alertas" variant="secondary" />
          <Avatar name={u.name} size="md" />
        </header>
        <main style={{ flex: 1, overflow: 'auto' }}>{children}</main>
      </div>
    </div>
  );
}

Object.assign(window, { AppShell });
