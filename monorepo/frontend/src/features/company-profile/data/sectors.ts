// Rubros de primer nivel de Mercado Público (Listado_rubros_ONU.xlsx, Datos Abiertos de
// ChileCompra, consultado el 2026-10-26), en el mismo orden que SECTOR_GROUPS del backend
// (monorepo/backend/app/shared/sectors.py).
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
    title: "Servicios",
    sectors: [
      "Consultoria",
      "Educación, formación, entrenamiento y capacitación",
      "Organizaciones sociales, laborales y clubes",
      "Salud, servicios sanitarios y alimentación",
      "Servicios agrícolas, pesqueros, forestales y relacionados con la fauna",
      "Servicios basados en ingeniería, ciencias sociales y tecnología de la información",
      "Servicios básicos y de información pública",
      "Servicios de Viajes, alimentación, alojamiento y entretenimiento",
      "Servicios de cuidado personal y domésticos",
      "Servicios de defensa nacional, orden público y seguridad",
      "Servicios de limpieza industrial",
      "Servicios de perforación de minería, petróleo y gas",
      "Servicios de producción y fabricación industrial",
      "Servicios de transporte, almacenaje y correo",
      "Servicios editoriales, de diseño, publicidad, gráficos y artistas",
      "Servicios financieros, pensiones y seguros",
      "Servicios medioambientales",
      "Servicios profesionales, administrativos y consultorías de gestión empresarial",
      "Tecnologías de la información, telecomunicaciones y radiodifusión",
    ],
  },
  {
    title: "Bienes",
    sectors: [
      "Alimentos, bebidas y tabaco",
      "Artículos de electrónica",
      "Artículos de fabricación y producción",
      "Artículos eléctricos y de iluminación",
      "Artículos para estructuras, obras y construcciones",
      "Artículos para plantas y animales",
      "Combustibles, lubricantes y anticorrosivos",
      "Equipamiento para el acondicionamiento, distribución y filtrado de fluidos",
      "Equipamiento para laboratorios",
      "Equipamiento para manejo y estiba de materiales",
      "Equipamiento y suministros médicos",
      "Equipos y suministros de defensa, orden público, protección y seguridad",
      "Equipos y suministros de imprenta, fotográficos y audiovisuales",
      "Equipos y suministros de limpieza",
      "Equipos, accesorios y suministros de oficina",
      "Equipos, suministros y accesorios deportivos y recreativos",
      "Herramientas y maquinaria en general",
      "Instrumentos musicales, juegos, juguetes, artesanías y materiales educativos",
      "Maquinaria para agricultura, pesca y silvicultura",
      "Maquinaria para construcción y edificación",
      "Maquinaria para fabricación y transformación industrial",
      "Maquinaria para generación y distribución de energía",
      "Maquinaria para minería y perforación",
      "Maquinarias, equipos y suministros para la industria de servicios",
      "Medicamentos y productos farmacéuticos",
      "Muebles y mobiliario",
      "Muebles, accesorios, electrodomésticos y productos electrónicos",
      "Productos de papel",
      "Productos derivados de minerales, plantas y animales",
      "Productos impresos y publicaciones",
      "Productos para relojería, joyería y gemas",
      "Productos químicos industriales",
      "Resinas, cauchos, espumas y elastómeros",
      "Ropa, maletas y productos de aseo personal",
      "Vehículos y equipamiento en general",
    ],
  },
  {
    title: "Obras y otros",
    sectors: [
      "Obras",
      "Obras MINVU",
      "Organizaciones y consultorías políticas, demográficas, económicas, sociales y de administración pública",
      "Servicios de construcción y mantenimiento",
    ],
  },
];

export const SECTORS: readonly string[] = SECTOR_GROUPS.flatMap((group) => group.sectors);
