// PerfilScreen — "Perfil inteligente" de la empresa.
const { Card, Badge, Tag, Button, Input, Select, MatchMeter, Avatar, Icon, Switch } = window.DS;

function Field({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.05em', textTransform: 'uppercase', color: 'var(--text-subtle)', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 'var(--text-base)', color: 'var(--text-strong)', fontWeight: 500 }}>{value}</div>
    </div>
  );
}

function PerfilScreen() {
  const D = window.PYDATA;
  const [alertas, setAlertas] = React.useState(true);
  return (
    <div style={{ padding: '28px 28px 56px', maxWidth: 920, margin: '0 auto' }}>
      <h1 style={{ fontSize: 'var(--text-4xl)', margin: '0 0 4px' }}>Mi empresa</h1>
      <p style={{ fontSize: 'var(--text-lg)', color: 'var(--text-muted)', margin: '0 0 24px' }}>
        Mientras más completo tu perfil, mejores serán tus matches.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24, alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <Card padding={22}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
              <Avatar name={D.user.company} shape="square" size="lg" />
              <div>
                <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 'var(--text-xl)', color: 'var(--text-strong)' }}>{D.user.company}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: 'var(--text-sm)' }}>RUT 76.842.193-4 · Pequeña empresa</div>
              </div>
              <div style={{ flex: 1 }} />
              <Button variant="secondary" iconLeft={<Icon name="pencil" size={16} />}>Editar</Button>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 18, paddingTop: 18, borderTop: '1px solid var(--border-subtle)' }}>
              <Field label="Región" value="Metropolitana" />
              <Field label="Comuna" value="Maipú" />
              <Field label="Actividad" value="Servicios de aseo" />
              <Field label="Inicio actividades" value="Marzo 2019" />
              <Field label="Tamaño" value="14 trabajadores" />
              <Field label="Estado SII" value="Al día" />
            </div>
          </Card>

          <Card padding={22}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <h3 style={{ fontSize: 'var(--text-lg)', margin: 0 }}>Rubros y servicios</h3>
              <span style={{ fontSize: 'var(--text-sm)', color: 'var(--text-subtle)' }}>Usados para el matching</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {D.rubros.map((r) => <Tag key={r} active onRemove={() => {}}>{r}</Tag>)}
              <Tag iconLeft={<Icon name="plus" size={15} />}>Agregar rubro</Tag>
            </div>
          </Card>

          <Card padding={22}>
            <h3 style={{ fontSize: 'var(--text-lg)', margin: '0 0 14px' }}>Documentos</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[['Certificado de inicio de actividades', true], ['Boletín comercial', true], ['Certificado de manejo de residuos', false]].map(([doc, ok]) => (
                <div key={doc} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', background: 'var(--bg-page)' }}>
                  <Icon name={ok ? 'file-check-2' : 'file-plus'} size={20} color={ok ? 'var(--teal-600)' : 'var(--text-subtle)'} />
                  <span style={{ flex: 1, fontSize: 'var(--text-sm)', color: 'var(--text-body)', fontWeight: 500 }}>{doc}</span>
                  {ok ? <Badge tone="success" dot>Cargado</Badge> : <Button variant="soft" size="sm">Subir</Button>}
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Right rail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, position: 'sticky', top: 88 }}>
          <Card padding={22} style={{ textAlign: 'center' }}>
            <MatchMeter value={D.profileStrength} size="lg" style={{ justifyContent: 'center' }} />
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 'var(--text-lg)', color: 'var(--text-strong)', marginTop: 10 }}>Fuerza del perfil</div>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', margin: '4px 0 16px' }}>Completa 1 documento para llegar a 100%.</p>
            <Button variant="primary" fullWidth iconRight={<Icon name="arrow-right" size={16} />}>Completar perfil</Button>
          </Card>
          <Card padding={20}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 10 }}>
              <Icon name="bell" size={20} color="var(--coral-500)" />
              <div style={{ fontWeight: 600, color: 'var(--text-strong)' }}>Alertas inteligentes</div>
            </div>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)', margin: '0 0 14px' }}>Te avisamos por correo cuando aparezca una licitación con alta compatibilidad.</p>
            <Switch checked={alertas} onChange={setAlertas} label="Activadas" />
          </Card>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { PerfilScreen });
