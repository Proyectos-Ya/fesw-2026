// Mock data for the ProyectosYa app UI kit. Fictional Compra Ágil tenders.
window.PYDATA = {
  user: { name: 'Camila Soto', company: 'Aseo Integral SpA', role: 'Representante legal' },
  profileStrength: 82,
  stats: { nuevas: 8, postuladas: 5, guardadas: 12, adjudicadas: 3 },
  rubros: ['Servicios de aseo', 'Mantención', 'Jardinería', 'Control de plagas'],
  licitaciones: [
    {
      id: '4982-117-LE25', match: 94, level: 'Alta',
      title: 'Servicios de aseo y mantención de recintos municipales',
      organismo: 'Municipalidad de Ñuñoa', region: 'Región Metropolitana',
      monto: '12.480.000', cierra: 3, status: 'abierta', rubro: 'Servicios de aseo',
      publicada: 'Hace 2 días',
      descripcion: 'Se requiere la contratación de servicios de aseo integral y mantención para tres recintos municipales, incluyendo personal, insumos y maquinaria, por un período de 12 meses renovables.',
      requisitos: ['Experiencia mínima 2 años en servicios similares', 'Personal con contrato vigente', 'Certificación de manejo de residuos', 'Inicio de actividades en SII'],
      analisis: {
        fuerte: [
          { t: 'Rubro exacto', d: 'Tu giro principal coincide con el objeto de la licitación.', v: 98 },
          { t: 'Experiencia comprobable', d: '4 contratos similares en tu historial.', v: 92 },
          { t: 'Cobertura geográfica', d: 'Operas en la Región Metropolitana.', v: 95 },
        ],
        brechas: [
          { t: 'Certificación de residuos', d: 'Adjunta tu certificado vigente para reforzar la postulación.' },
        ],
      },
    },
    {
      id: '5103-204-LP25', match: 88, level: 'Alta',
      title: 'Mantención de áreas verdes y poda de árboles',
      organismo: 'Servicio de Vivienda y Urbanización RM', region: 'Región Metropolitana',
      monto: '8.900.000', cierra: 5, status: 'abierta', rubro: 'Jardinería',
      publicada: 'Hace 1 día',
      descripcion: 'Mantención periódica de áreas verdes, poda y retiro de ramas en conjuntos habitacionales.',
      requisitos: ['Cuadrilla con herramientas propias', 'Seguro de responsabilidad civil'],
      analisis: { fuerte: [{ t: 'Rubro relacionado', d: 'Jardinería está en tus rubros declarados.', v: 88 }], brechas: [] },
    },
    {
      id: '4771-330-CM25', match: 72, level: 'Media',
      title: 'Control de plagas en establecimientos educacionales',
      organismo: 'Corporación Municipal de Maipú', region: 'Región Metropolitana',
      monto: '5.200.000', cierra: 8, status: 'abierta', rubro: 'Control de plagas',
      publicada: 'Hace 3 días',
      descripcion: 'Servicio de desratización y desinsectación en 12 establecimientos educacionales.',
      requisitos: ['Resolución sanitaria vigente', 'Aplicadores certificados'],
      analisis: { fuerte: [{ t: 'Rubro declarado', d: 'Control de plagas figura en tu perfil.', v: 80 }], brechas: [{ t: 'Resolución sanitaria', d: 'No tenemos registro de tu resolución vigente.' }] },
    },
    {
      id: '3920-088-LE25', match: 58, level: 'Baja',
      title: 'Suministro de insumos de limpieza',
      organismo: 'Hospital Sótero del Río', region: 'Región Metropolitana',
      monto: '3.100.000', cierra: 11, status: 'abierta', rubro: 'Suministro',
      publicada: 'Hace 4 días',
      descripcion: 'Compra de insumos de limpieza e higiene para servicios clínicos.',
      requisitos: ['Distribuidor autorizado'],
      analisis: { fuerte: [], brechas: [{ t: 'Giro de suministro', d: 'Tu empresa presta servicios, no suministra productos.' }] },
    },
  ],
};
