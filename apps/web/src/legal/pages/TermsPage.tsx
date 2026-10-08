import { PROJECT_REPOSITORY } from '../../lib/project-links';

export function TermsPage() {
  return (
    <article className="legal-page">
      <p className="eyebrow">Información del proyecto</p>
      <h1>Términos y condiciones</h1>
      <p className="legal-lead">
        Red energía es un proyecto independiente de código abierto para explorar
        información sobre el mercado eléctrico de España.
      </p>
      <section>
        <h2>Independencia</h2>
        <p>
          No estamos afiliados a la Comisión Nacional de los Mercados y la Competencia
          (CNMC), a ninguna distribuidora ni a ninguna comercializadora. Tampoco actuamos
          en su nombre. Citar sus datos o mostrar nombres de empresas no implica
          patrocinio, aprobación ni respaldo de esas entidades.
        </p>
      </section>
      <section>
        <h2>Finalidad y límites de la información</h2>
        <p>
          La información se ofrece con fines informativos. No constituye una oferta
          comercial, una recomendación de contratación ni una confirmación de qué
          distribuidora atiende un domicilio. Para gestiones o decisiones sobre tu
          suministro, consulta tu factura y las fuentes oficiales correspondientes.
        </p>
        <p>
          Los datos pueden contener errores, revisiones o retrasos. La presencia
          documentada de una distribuidora en una provincia no demuestra cobertura
          en todos sus municipios. La falta de evidencia no significa ausencia de
          red. Los límites del mapa son una instantánea actual y las cuotas de mercado
          se muestran únicamente para el ámbito territorial disponible.
        </p>
      </section>
      <section>
        <h2>Fuentes y reutilización</h2>
        <p>
          Cada conjunto conserva sus fuentes, fechas y condiciones de reutilización.
          Origen de los datos de mercado: Comisión Nacional de los Mercados y la
          Competencia. Sus derivados mantienen la licencia CC BY-SA 4.0 y deben
          respetar las{' '}
          <a href="https://data.cnmc.es/condiciones-de-uso" target="_blank" rel="noreferrer">
            condiciones de CNMC Data
          </a>.
        </p>
        <p>
          La cartografía procede del IGN/CNIG y utiliza códigos territoriales del INE.
        </p>
        <p>
          El código original se distribuye bajo AGPL-3.0-only, sin garantía, conforme
          a su licencia. Esa licencia no se extiende automáticamente a los datos,
          documentos, cartografía o marcas de terceros. La evidencia de distribución
          conserva las condiciones de cada fuente.
        </p>
      </section>
      <section>
        <h2>Disponibilidad y correcciones</h2>
        <p>
          El proyecto se mantiene con los recursos disponibles y puede cambiar o
          sufrir interrupciones. No se garantiza que la información esté completa
          o actualizada en todo momento. Si encuentras un error, puedes comunicarlo
          en el{' '}
          <a href={PROJECT_REPOSITORY} target="_blank" rel="noreferrer">repositorio de GitHub</a>,
          indicando la fuente y evitando publicar datos personales, facturas o
          identificadores de suministro.
        </p>
      </section>
    </article>
  );
}
