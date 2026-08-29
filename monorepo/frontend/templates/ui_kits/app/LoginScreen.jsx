// LoginScreen — split-panel sign in for the ProyectosYa app.
const { Button, Input, Checkbox, Badge, Card, MatchMeter, Avatar, Icon } = window.DS;

function BrandPanel() {
  return (
    <div style={{
      position: 'relative', overflow: 'hidden', background: 'var(--teal-600)',
      padding: '48px 52px', display: 'flex', flexDirection: 'column', minHeight: '100%',
    }}>
      {/* texture circles */}
      <div style={{ position: 'absolute', right: -90, top: -90, width: 320, height: 320, borderRadius: '50%', background: 'var(--teal-500)', opacity: 0.45 }} />
      <div style={{ position: 'absolute', right: 60, bottom: -120, width: 260, height: 260, borderRadius: '50%', background: 'var(--teal-700)', opacity: 0.5 }} />

      <img src="../../assets/logo-wordmark-onteal.svg" alt="ProyectosYa" style={{ height: 32, position: 'relative', zIndex: 2 }} />

      <div style={{ position: 'relative', zIndex: 2, marginTop: 'auto' }}>
        <h2 style={{ color: 'var(--warm-50)', fontSize: 'var(--text-5xl)', lineHeight: 1.05, letterSpacing: '-0.02em', margin: '0 0 16px', maxWidth: 420 }}>
          Postula a la licitación <span style={{ color: 'var(--coral-300)' }}>correcta</span>, hoy.
        </h2>
        <p style={{ color: 'var(--teal-100)', fontSize: 'var(--text-lg)', margin: '0 0 32px', maxWidth: 380 }}>
          Tus oportunidades de Compra Ágil, filtradas por IA y ordenadas por compatibilidad.
        </p>

        {/* floating match card */}
        <Card padding={16} elevation="lg" style={{ maxWidth: 360, display: 'flex', gap: 14, alignItems: 'center' }}>
          <MatchMeter value={94} size="md" />
          <div style={{ flex: 1, minWidth: 0 }}>
            <Badge tone="teal" style={{ marginBottom: 6 }}>Nuevo match</Badge>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: 'var(--text-base)', color: 'var(--text-strong)', lineHeight: 1.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              Aseo y mantención municipal
            </div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>Municipalidad de Ñuñoa</div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function LoginScreen({ onSubmit }) {
  const [usuario, setUsuario] = React.useState('');
  const [pass, setPass] = React.useState('');
  const [show, setShow] = React.useState(false);
  const [remember, setRemember] = React.useState(true);

  return (
    <div style={{
      minHeight: '100vh', display: 'grid', gridTemplateColumns: '1.05fr 1fr',
      background: 'var(--bg-page)',
    }}>
      <BrandPanel />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px' }}>
        <div style={{ width: '100%', maxWidth: 380 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>Bienvenido de vuelta</div>
          <h1 style={{ fontSize: 'var(--text-4xl)', margin: '0 0 8px' }}>Inicia sesión</h1>
          <p style={{ color: 'var(--text-muted)', margin: '0 0 28px' }}>
            Entra para ver tus licitaciones compatibles de hoy.
          </p>

          <form onSubmit={(e) => { e.preventDefault(); onSubmit && onSubmit(); }} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <Input
              label="RUT o correo" placeholder="76.842.193-4"
              value={usuario} onChange={(e) => setUsuario(e.target.value)}
              iconLeft={<Icon name="user" size={18} />}
            />
            <div>
              <Input
                label="Contraseña" placeholder="••••••••" type={show ? 'text' : 'password'}
                value={pass} onChange={(e) => setPass(e.target.value)}
                iconLeft={<Icon name="lock" size={18} />}
              />
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
                <Checkbox checked={remember} onChange={setRemember} label="Recordarme" />
                <a href="#" style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>¿Olvidaste tu contraseña?</a>
              </div>
            </div>

            <Button type="submit" variant="primary" size="lg" fullWidth iconRight={<Icon name="arrow-right" size={18} />}>
              Iniciar sesión
            </Button>
          </form>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '22px 0' }}>
            <span style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>o continúa con</span>
            <span style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
          </div>

          <Button variant="secondary" size="lg" fullWidth iconLeft={<Icon name="shield-check" size={18} />}>
            ClaveÚnica
          </Button>

          <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 'var(--text-sm)', marginTop: 28 }}>
            ¿No tienes cuenta? <a href="#" style={{ fontWeight: 600 }}>Crea tu perfil gratis</a>
          </p>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { LoginScreen });
