// DashboardScreen — "Para ti" matched-tender feed.
const { Card, Tabs, Tag, Select, MatchMeter, Icon, Button } = window.DS;

function StatTile({ icon, value, label, tone }) {
  return (
    <Card padding={16} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <span style={{ width: 40, height: 40, borderRadius: 'var(--radius-md)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', background: tone.bg, flex: 'none' }}>
        <Icon name={icon} size={20} color={tone.fg} />
      </span>
      <div>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 'var(--text-2xl)', color: 'var(--text-strong)', lineHeight: 1 }}>{value}</div>
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>{label}</div>
      </div>
    </Card>
  );
}

function DashboardScreen({ onOpen, saved, onToggleSave }) {
  const D = window.PYDATA;
  const [tab, setTab] = React.useState('match');
  const [rubro, setRubro] = React.useState('Todos');
  const list = D.licitaciones;
  return (
    <div style={{ padding: '28px 28px 48px', maxWidth: 920, margin: '0 auto' }}>
      <div style={{ marginBottom: 20 }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>Lunes 9 de junio</div>
        <h1 style={{ fontSize: 'var(--text-4xl)', margin: '0 0 6px' }}>Hola, {D.user.name.split(' ')[0]}</h1>
        <p style={{ fontSize: 'var(--text-lg)', color: 'var(--text-muted)', margin: 0 }}>
          Encontramos <strong style={{ color: 'var(--text-strong)' }}>{D.stats.nuevas} licitaciones nuevas</strong> que calzan con tu perfil esta semana.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 14, marginBottom: 24 }}>
        <StatTile icon="sparkles" value={D.stats.nuevas} label="Nuevas para ti" tone={{ bg: 'var(--teal-50)', fg: 'var(--teal-600)' }} />
        <StatTile icon="send" value={D.stats.postuladas} label="Postuladas" tone={{ bg: 'var(--coral-50)', fg: 'var(--coral-600)' }} />
        <StatTile icon="bookmark" value={D.stats.guardadas} label="Guardadas" tone={{ bg: 'var(--warm-100)', fg: 'var(--text-muted)' }} />
        <StatTile icon="trophy" value={D.stats.adjudicadas} label="Adjudicadas" tone={{ bg: 'var(--success-soft)', fg: 'var(--green-600)' }} />
      </div>

      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, marginBottom: 16, flexWrap: 'wrap' }}>
        <Tabs value={tab} onChange={setTab} tabs={[
          { value: 'match', label: 'Para ti', count: D.stats.nuevas },
          { value: 'todas', label: 'Todas', count: 142 },
          { value: 'cierran', label: 'Cierran pronto' },
        ]} />
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <Select value={rubro} onChange={setRubro} options={['Todos', ...D.rubros]} style={{ width: 200 }} />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {list.map((lic) => (
          <window.LicitacionCard key={lic.id} lic={lic} onOpen={onOpen} saved={saved.includes(lic.id)} onToggleSave={onToggleSave} />
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { DashboardScreen });
