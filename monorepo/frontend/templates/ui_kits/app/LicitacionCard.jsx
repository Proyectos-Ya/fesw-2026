// LicitacionCard — feed row for a tender. Used in the dashboard.
const { Card, Badge, Tag, Button, MatchMeter, IconButton, Icon } = window.DS;

function deadlineTone(d) { return d <= 3 ? 'warning' : d <= 7 ? 'neutral' : 'neutral'; }

function LicitacionCard({ lic, onOpen, saved, onToggleSave }) {
  return (
    <Card interactive padding={20} onClick={() => onOpen(lic)} style={{ display: 'flex', gap: 18, alignItems: 'flex-start' }}>
      <MatchMeter value={lic.match} size="lg" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
          <Badge tone="teal">Compra Ágil</Badge>
          <Badge tone={deadlineTone(lic.cierra)} dot={lic.cierra <= 3}>
            {lic.cierra <= 3 ? `Cierra en ${lic.cierra} días` : `Cierra en ${lic.cierra} días`}
          </Badge>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-subtle)' }}>ID {lic.id}</span>
        </div>
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 'var(--text-xl)', color: 'var(--text-strong)', lineHeight: 1.2, letterSpacing: '-0.01em' }}>{lic.title}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 6, color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>
          <Icon name="building-2" size={15} color="var(--text-subtle)" />
          <span>{lic.organismo}</span>
          <span style={{ color: 'var(--border-strong)' }}>·</span>
          <Icon name="map-pin" size={15} color="var(--text-subtle)" />
          <span>{lic.region}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 14, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Monto estimado</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}>${lic.monto}</div>
          </div>
          <Tag>{lic.rubro}</Tag>
          <div style={{ flex: 1 }} />
          <IconButton icon={<Icon name={saved ? 'bookmark-check' : 'bookmark'} size={18} />} label="Guardar"
            variant={saved ? 'primary' : 'secondary'} onClick={(e) => { e.stopPropagation(); onToggleSave(lic.id); }} />
          <Button variant="soft" iconRight={<Icon name="arrow-right" size={16} />} onClick={(e) => { e.stopPropagation(); onOpen(lic); }}>Ver análisis</Button>
        </div>
      </div>
    </Card>
  );
}

Object.assign(window, { LicitacionCard });
