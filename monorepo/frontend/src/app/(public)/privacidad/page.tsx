import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chiripa - Política de privacidad",
  description: "Qué datos recoge Chiripa, para qué los usa y cómo eliminarlos.",
};

/** Última revisión del texto. Si se cambia el contenido, se cambia esta fecha. */
const ULTIMA_ACTUALIZACION = "8 de septiembre de 2026";

const CORREO_CONTACTO = "luislopezaguilera42@gmail.com";

function Seccion({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-10">
      <h2 className="text-xl font-bold text-text-strong mb-3">{titulo}</h2>
      <div className="flex flex-col gap-3 text-text-body leading-relaxed">
        {children}
      </div>
    </section>
  );
}

export default function PrivacidadPage() {
  return (
    <article>
      <div className="eyebrow mb-2">Legal</div>
      <h1 className="text-4xl font-bold text-text-strong mb-3">
        Política de privacidad
      </h1>
      <p className="text-text-muted">
        Última actualización: {ULTIMA_ACTUALIZACION}
      </p>

      <Seccion titulo="Qué es Chiripa">
        <p>
          Chiripa es una plataforma que compara el perfil de una empresa con las
          licitaciones publicadas en Mercado Público (ChileCompra) y le avisa
          cuáles le calzan. Para eso necesita saber a qué se dedica tu empresa,
          y ese es el origen de casi todos los datos que se describen acá.
        </p>
      </Seccion>

      <Seccion titulo="Qué datos recogemos">
        <p>
          <strong>De tu cuenta.</strong> Tu dirección de correo y tu nombre. Si
          entras con Google, los entrega Google al iniciar sesión; si te
          registras con correo y contraseña, los escribes tú. La contraseña no
          la almacenamos nosotros: la guarda nuestro proveedor de
          autenticación, y nunca llega a nuestros servidores en texto legible.
          El teléfono es opcional.
        </p>
        <p>
          <strong>De tu empresa.</strong> RUT, razón social, nombre de fantasía,
          descripción de la actividad, regiones donde operas, rubros,
          certificaciones, palabras clave, años de experiencia y número de
          trabajadores. Todo esto lo escribes tú al configurar el perfil, y es
          lo que alimenta la comparación con las licitaciones.
        </p>
        <p>
          <strong>Documentos que subes.</strong> Si usas el asistente de
          licitaciones, los archivos que adjuntes se guardan junto con su
          nombre, tipo y tamaño, asociados a tu cuenta.
        </p>
        <p>
          <strong>De tu uso de la plataforma.</strong> Licitaciones que guardas,
          avisos que se te generaron y si los leíste, tus preferencias de
          alertas, y el historial de tus conversaciones con el asistente.
        </p>
        <p>
          No recogemos datos de tarjetas ni medios de pago, no usamos cookies de
          publicidad ni de seguimiento de terceros, y no compramos ni vendemos
          bases de datos de contactos.
        </p>
      </Seccion>

      <Seccion titulo="Para qué los usamos">
        <ul className="list-disc pl-5 flex flex-col gap-2">
          <li>
            Comparar tu perfil con las licitaciones y calcular qué tan
            compatibles son.
          </li>
          <li>
            Avisarte por correo cuando aparece una licitación compatible, si
            tienes esa opción activada.
          </li>
          <li>
            Responder tus consultas sobre una licitación con el asistente.
          </li>
          <li>Mantener tu sesión iniciada y proteger tu cuenta.</li>
        </ul>
        <p>
          No usamos tus datos para ningún otro fin, ni los cedemos a terceros
          para que los usen por su cuenta.
        </p>
      </Seccion>

      <Seccion titulo="Con quién se comparten">
        <p>
          Para funcionar, Chiripa se apoya en servicios de terceros que procesan
          datos por encargo nuestro:
        </p>
        <ul className="list-disc pl-5 flex flex-col gap-2">
          <li>
            <strong>Supabase</strong> — autenticación y base de datos. Ahí viven
            tu cuenta y tu perfil.
          </li>
          <li>
            <strong>Google</strong> — solo si eliges entrar con tu cuenta de
            Google. Nos entrega tu correo, tu nombre y tu foto de perfil; no
            recibe nada tuyo de vuelta.
          </li>
          <li>
            <strong>Google Gemini</strong> — el modelo de inteligencia
            artificial que redacta el análisis de compatibilidad y responde en
            el asistente. Recibe el texto de la licitación, la descripción de tu
            empresa y los documentos que adjuntes a una consulta.
          </li>
          <li>
            <strong>Brevo</strong> — envío de los correos de confirmación de
            cuenta y de las alertas. Recibe tu dirección de correo.
          </li>
          <li>
            <strong>Railway</strong> y <strong>Vercel</strong> — alojamiento de
            la aplicación.
          </li>
        </ul>
        <p>
          Las licitaciones provienen de la API pública de Mercado Público. Esa
          información es pública y no contiene datos tuyos: la consultamos, no
          le enviamos nada.
        </p>
      </Seccion>

      <Seccion titulo="Cuánto tiempo los guardamos">
        <p>
          Mientras tengas la cuenta activa. Si la eliminas, borramos tu perfil,
          tus licitaciones guardadas, tus conversaciones, los documentos que
          subiste y tu historial de alertas.
        </p>
      </Seccion>

      <Seccion titulo="Tus derechos">
        <p>
          Puedes pedirnos acceder a tus datos, corregirlos, eliminarlos, o pedir
          una copia. Escríbenos a{" "}
          <a
            href={`mailto:${CORREO_CONTACTO}`}
            className="font-semibold text-primary hover:text-primary-hover"
          >
            {CORREO_CONTACTO}
          </a>{" "}
          y responderemos dentro de un plazo razonable.
        </p>
        <p>
          Para dejar de recibir correos de alertas no hace falta escribirnos: se
          apagan desde <strong>Preferencias de alertas</strong>, dentro de la
          aplicación.
        </p>
      </Seccion>

      <Seccion titulo="Seguridad">
        <p>
          El acceso a la aplicación requiere sesión iniciada, y cada petición se
          valida en el servidor. La conexión viaja cifrada. Aun así, ningún
          sistema es infalible: si detectamos un incidente que afecte tus datos,
          te avisaremos.
        </p>
      </Seccion>

      <Seccion titulo="Cambios a esta política">
        <p>
          Si cambiamos algo relevante, actualizaremos la fecha del encabezado y
          te avisaremos por correo o dentro de la aplicación.
        </p>
      </Seccion>

      <Seccion titulo="Contacto">
        <p>
          Dudas sobre esta política o sobre tus datos:{" "}
          <a
            href={`mailto:${CORREO_CONTACTO}`}
            className="font-semibold text-primary hover:text-primary-hover"
          >
            {CORREO_CONTACTO}
          </a>
          .
        </p>
      </Seccion>
    </article>
  );
}
