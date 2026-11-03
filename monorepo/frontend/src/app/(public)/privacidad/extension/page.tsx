import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chiripa - Política de Privacidad de la Extensión",
  description:
    "Política de privacidad y tratamiento de datos para la extensión de navegador de Chiripa (Chrome Web Store y Firefox AMO).",
};

const ULTIMA_ACTUALIZACION = "3 de noviembre de 2026";
const CORREO_CONTACTO = "contacto@chiripa.cl";

function Seccion({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-8">
      <h2 className="text-xl font-bold text-text-strong mb-3">{titulo}</h2>
      <div className="flex flex-col gap-3 text-text-body leading-relaxed">{children}</div>
    </section>
  );
}

export default function PrivacidadExtensionPage() {
  return (
    <article className="max-w-3xl mx-auto py-10 px-4">
      <div className="eyebrow mb-2">Legal y Tiendas de Extensiones</div>
      <h1 className="text-3xl font-bold text-text-strong mb-2">
        Política de Privacidad de la Extensión Oficial de Chiripa
      </h1>
      <p className="text-sm text-text-muted mb-6">
        Última actualización: {ULTIMA_ACTUALIZACION}
      </p>

      <Seccion titulo="1. Propósito de la extensión">
        <p>
          La extensión de navegador de Chiripa (disponible para Google Chrome, Microsoft Edge y Mozilla Firefox)
          tiene como único objetivo asistir a los usuarios de Chiripa en el proceso de postulación a licitaciones
          y cotizaciones en Mercado Público (ChileCompra), permitiendo transferir automáticamente los ítems, valores y
          archivos adjuntos elaborados en Chiripa directamente al formulario correspondiente de Mercado Público.
        </p>
      </Seccion>

      <Seccion titulo="2. Credenciales y Contraseñas (Garantía de Seguridad)">
        <p>
          <strong>Nunca leemos, solicitamos ni almacenamos tus contraseñas de Mercado Público ni de ClaveÚnica.</strong>
        </p>
        <p>
          La extensión no cuenta con permisos ni capacidades técnicas para interactuar con campos de contraseña
          ni con formularios de inicio de sesión de ClaveÚnica o Mercado Público. El usuario siempre inicia sesión
          directa y manualmente en Mercado Público sin intervención alguna de la extensión.
        </p>
      </Seccion>

      <Seccion titulo="3. Datos tratados por la extensión">
        <p>
          La extensión opera con el principio de mínimo privilegio y trata únicamente:
        </p>
        <ul className="list-disc pl-5 flex flex-col gap-1.5 text-sm">
          <li>
            <strong>Datos de la postulación activa:</strong> Código de licitación, RUT y razón social de tu empresa,
            valores netos cotizados por ítem, descripción de la propuesta y documentos anexos seleccionados.
          </li>
          <li>
            <strong>Almacenamiento temporal en tu navegador:</strong> Estos datos se almacenan localmente en la memoria
            del navegador (IndexedDB y almacenamiento local de la extensión) con una caducidad automática estricta de 30 minutos.
            No se transfieren a servidores de terceros ni se comparten con otras entidades.
          </li>
          <li>
            <strong>Cookies e historial:</strong> La extensión no accede a tus cookies de navegación ni registra tu historial de navegación.
          </li>
        </ul>
      </Seccion>

      <Seccion titulo="4. Cero envío automático (Control 100% en manos del usuario)">
        <p>
          La extensión se limita a rellenar los campos del formulario y resaltar los datos cargados para facilitar su revisión.
          <strong> La extensión jamás hace clic en botones de envío definitivo de la oferta ni acepta declaraciones juradas por ti.</strong>
        </p>
        <p>
          La revisión final, aceptación de condiciones y el envío de la postulación en Mercado Público siempre deben ser
          realizados explícita y manualmente por el usuario responsable de la empresa proveedora.
        </p>
      </Seccion>

      <Seccion titulo="5. Contacto y ejercicio de derechos">
        <p>
          Si tienes preguntas sobre la seguridad o el tratamiento de datos de la extensión, puedes comunicarte directamente con nuestro equipo en{" "}
          <a href={`mailto:${CORREO_CONTACTO}`} className="font-semibold text-primary underline">
            {CORREO_CONTACTO}
          </a>.
        </p>
      </Seccion>
    </article>
  );
}
