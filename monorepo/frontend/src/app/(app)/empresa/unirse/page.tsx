import Link from "next/link";

// Placeholder: la membresía a empresas existentes aún no está implementada.
export default function UnirseEmpresaPage() {
  return (
    <section className="flex flex-1 flex-col items-center justify-center text-center py-24">
      <h1 className="font-display text-3xl font-extrabold tracking-tight text-text-strong">
        Unirse a una empresa
      </h1>
      <p className="mt-4 max-w-md text-text-muted leading-relaxed">
        Muy pronto podrás pedir unirte al equipo de una empresa que ya está en
        ProyectosYA.
      </p>
      <Link
        href="/"
        className="mt-8 rounded-full bg-primary px-8 py-3 text-sm font-bold text-white transition-all hover:bg-primary-hover"
      >
        Volver al inicio
      </Link>
    </section>
  );
}
