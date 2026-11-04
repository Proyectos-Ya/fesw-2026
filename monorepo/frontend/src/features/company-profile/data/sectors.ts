// Rubros de primer nivel de Mercado Público (Listado_rubros_ONU.xlsx, Datos Abiertos de
// ChileCompra, consultado el 2026-10-26), en el mismo orden que SECTOR_GROUPS del backend
// (monorepo/backend/app/shared/sectors.py).
// Los grupos son los rangos de segmentos UNSPSC, con Tecnologías de la información en
// Servicios y un grupo aparte para las categorías propias de ChileCompra; el docstring
// del backend explica el criterio.
//
// Formato fijo: un test del backend lee este archivo con expresiones regulares y falla si
// los títulos, los nombres o su orden no coinciden con el backend. Por eso:
// - cada grupo abre con una línea title: seguida del título entre comillas dobles;
// - cada rubro va en su propia línea, entre comillas dobles, seguido de una coma;
// - no se usan comillas simples, backticks ni comentarios dentro de la lista;
// - esta cabecera no lleva comillas dobles, para que el test no la confunda con datos.

export interface SectorGroup {
  title: string;
  sectors: readonly string[];
}

export const SECTOR_GROUPS: readonly SectorGroup[] = [
  {
    title: "Materias primas",
    sectors: [
      "Artículos para plantas y animales",
      "Productos derivados de minerales, plantas y animales",
      "Productos químicos industriales",
      "Resinas, cauchos, espumas y elastómeros",
      "Productos de papel",
      "Combustibles, lubricantes y anticorrosivos",
    ],
  },
  {
    title: "Maquinaria y equipamiento industrial",
    sectors: [
      "Maquinaria para minería y perforación",
      "Maquinaria para agricultura, pesca y silvicultura",
      "Maquinaria para construcción y edificación",
      "Maquinaria para fabricación y transformación industrial",
      "Equipamiento para manejo y estiba de materiales",
      "Vehículos y equipamiento en general",
      "Maquinaria para generación y distribución de energía",
      "Herramientas y maquinaria en general",
    ],
  },
  {
    title: "Componentes y suministros",
    sectors: [
      "Artículos para estructuras, obras y construcciones",
      "Artículos de fabricación y producción",
      "Artículos de electrónica",
      "Artículos eléctricos y de iluminación",
      "Equipamiento para el acondicionamiento, distribución y filtrado de fluidos",
      "Equipamiento para laboratorios",
    ],
  },
  {
    title: "Productos de uso final",
    sectors: [
      "Equipamiento y suministros médicos",
      "Equipos, accesorios y suministros de oficina",
      "Equipos y suministros de imprenta, fotográficos y audiovisuales",
      "Equipos y suministros de defensa, orden público, protección y seguridad",
      "Equipos y suministros de limpieza",
      "Maquinarias, equipos y suministros para la industria de servicios",
      "Equipos, suministros y accesorios deportivos y recreativos",
      "Alimentos, bebidas y tabaco",
      "Medicamentos y productos farmacéuticos",
      "Muebles, accesorios, electrodomésticos y productos electrónicos",
      "Ropa, maletas y productos de aseo personal",
      "Productos para relojería, joyería y gemas",
      "Productos impresos y publicaciones",
      "Muebles y mobiliario",
      "Instrumentos musicales, juegos, juguetes, artesanías y materiales educativos",
    ],
  },
  {
    title: "Servicios",
    sectors: [
      "Tecnologías de la información, telecomunicaciones y radiodifusión",
      "Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",
      "Servicios de perforación de minería, petróleo y gas",
      "Servicios de construcción y mantenimiento",
      "Servicios de producción y fabricación industrial",
      "Servicios de limpieza industrial",
      "Servicios medioambientales",
      "Servicios de transporte, almacenaje y correo",
      "Servicios profesionales, administrativos y consultorías de gestión empresarial",
      "Servicios basados en ingeniería, ciencias sociales y tecnología de la información",
      "Servicios editoriales, de diseño, publicidad, gráficos y artistas",
      "Servicios básicos y de información pública",
      "Servicios financieros, pensiones y seguros",
      "Salud, servicios sanitarios y alimentación",
      "Educación, formación, entrenamiento y capacitación",
      "Servicios de Viajes, alimentación, alojamiento y entretenimiento",
      "Servicios de cuidado personal y domésticos",
      "Servicios de defensa nacional, orden público y seguridad",
      "Organizaciones y consultorías políticas, demográficas, económicas, sociales y de administración pública",
      "Organizaciones sociales, laborales y clubes",
    ],
  },
  {
    title: "Obras y consultorías de ChileCompra",
    sectors: [
      "Consultoria",
      "Obras",
      "Obras MINVU",
    ],
  },
];

export const SECTORS: readonly string[] = SECTOR_GROUPS.flatMap((group) => group.sectors);
