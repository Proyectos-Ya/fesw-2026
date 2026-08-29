// LicitacionDetailScreen — full tender view with AI compatibility analysis.
const { Card, Badge, Tag, Button, MatchMeter, Icon, IconButton } = window.DS;

function AnalysisRow({ item, kind }) {
  const good = kind === 'fuerte';
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '12px 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <span style={{
        width: 28, height: 28, borderRadius: '50%', flex: 'none', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        background: good ? 'var(--success-soft)' : 'var(--warning-soft)',
      }}>
        <Icon name={good ? 'check' : 'alert-triangle'} size={16} color={good ? 'var(--green-600)' : 'var(--amber-600)'} />
      </span>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
          <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--text-strong)' }}>{item.t}</span>
          {good && item.v != null && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--teal-600)' }}>{item.v}%</span>}
        </div>
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', marginTop: 2 }}>{item.d}</div>
      </div>
    </div>
  );
}

function DetailScreen({ lic, onBack, saved, onToggleSave }) {
  const a = lic.analisis;
  return (
    <div style={{ padding: '24px 28px 56px', maxWidth: 960, margin: '0 auto' }}>
      <button onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--text-muted)', fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)', fontWeight: 600, padding: '4px 0', marginBottom: 16 }}>
        <Icon name="arrow-left" size={16} /> Volver a oportunidades
      </button>

      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
        <Badge tone="teal">Compra Ágil</Badge>
        <Badge tone="warning" dot>Cierra en {lic.cierra} días</Badge>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--text-subtle)' }}>ID {lic.id}</span>
      </div>
      <h1 style={{ fontSize: 'var(--text-3xl)', margin: '0 0 10px', maxWidth: 720 }}>{lic.title}</h1>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 'var(--text-base)', marginBottom: 24 }}>
        <Icon name="building-2" size={17} color="var(--text-subtle)" /><span>{lic.organismo}</span>
        <span style={{ color: 'var(--border-strong)' }}>·</span>
        <Icon name="map-pin" size={17} color="var(--text-subtle)" /><span>{lic.region}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24, alignItems: 'start' }}>
        {/* Left column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* AI analysis */}
          <Card padding={22} style={{ borderColor: 'var(--teal-200)', background: 'linear-gradient(180deg, var(--teal-50), var(--surface-card) 64%)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
              <span style={{ width: 34, height: 34, borderRadius: 'var(--radius-md)', background: 'var(--primary)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
                <Icon name="sparkles" size={19} color="#fff" />
              </span>
              <div>
                <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 'var(--text-lg)', color: 'var(--text-strong)' }}>Análisis de compatibilidad</div>
                <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>Cruzamos esta licitación con tu perfil de empresa.</div>
              </div>
            </div>
            {a.fuerte.length > 0 && <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--green-600)', marginTop: 16 }}>Por qué calza contigo</div>}
            {a.fuerte.map((it, i) => <AnalysisRow key={i} item={it} kind="fuerte" />)}
            {a.brechas.length > 0 && <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--amber-600)', marginTop: 16 }}>Brechas a cubrir</div>}
            {a.brechas.map((it, i) => <AnalysisRow key={i} item={it} kind="brecha" />)}
          </Card>

          {/* Description */}
          <Card padding={22}>
            <h3 style={{ fontSize: 'var(--text-lg)', margin: '0 0 8px' }}>Descripción</h3>
            <p style={{ color: 'var(--text-body)', margin: 0, lineHeight: 1.6 }}>{lic.descripcion}</p>
            <h3 style={{ fontSize: 'var(--text-lg)', margin: '20px 0 10px' }}>Requisitos</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {lic.requisitos.map((r, i) => (
                <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                  <Icon name="check-circle-2" size={18} color="var(--teal-500)" style={{ marginTop: 1 }} />
                  <span style={{ color: 'var(--text-body)', fontSize: 'var(--text-base)' }}>{r}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Sticky action rail */}
        <div style={{ position: 'sticky', top: 88, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Card padding={22} style={{ textAlign: 'center' }}>
            <MatchMeter value={lic.match} size="lg" style={{ justifyContent: 'center', marginBottom: 4 }} />
            <div style={{ fontWeight: 600, color: 'var(--teal-600)', marginTop: 8 }}>Compatibilidad {lic.level.toLowerCase()}</div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', marginBottom: 16 }}>Buenas opciones de adjudicación.</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderTop: '1px solid var(--border-subtle)', borderBottom: '1px solid var(--border-subtle)' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>Monto estimado</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-strong)' }}>${lic.monto}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--border-subtle)', marginBottom: 16 }}>
              <span style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>Cierra</span>
              <span style={{ fontWeight: 600, color: 'var(--amber-600)' }}>en {lic.cierra} días</span>
            </div>
            <Button variant="accent" size="lg" fullWidth iconRight={<Icon name="arrow-right" size={18} />}>Postular ahora</Button>
            <Button variant="secondary" fullWidth style={{ marginTop: 10 }}
              iconLeft={<Icon name={saved ? 'bookmark-check' : 'bookmark'} size={18} />}
              onClick={() => onToggleSave(lic.id)}>
              {saved ? 'Guardada' : 'Guardar'}
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { DetailScreen });
