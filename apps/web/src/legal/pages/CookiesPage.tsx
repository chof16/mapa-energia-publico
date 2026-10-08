import { Link } from 'react-router';

export function CookiesPage() {
  return (
    <article className="legal-page">
      <p className="eyebrow">Información del proyecto</p>
      <h1>Cookies y almacenamiento</h1>
      <p className="legal-lead">
        La aplicación no instala cookies ni incorpora herramientas de analítica,
        publicidad o seguimiento de visitantes.
      </p>
      <section>
        <h2>Cómo se guardan tus selecciones</h2>
        <p>
          El territorio, el trimestre y los filtros que puedes compartir se guardan
          en la dirección de la página. Las consultas y otros ajustes temporales se
          mantienen en memoria mientras usas la aplicación. No usamos almacenamiento
          local del navegador para crear identificadores de seguimiento.
        </p>
        <p>
          El navegador puede conservar archivos en su caché y direcciones en su
          historial según tu configuración. Esto es distinto de instalar cookies.
        </p>
      </section>
      <section>
        <h2>Recursos y enlaces externos</h2>
        <p>
          Para mostrar la información, el navegador solicita datos, mapas y fuentes
          tipográficas a los servidores que los proporcionan. Las tipografías de la
          interfaz se cargan desde Google Fonts y las etiquetas del mapa desde
          OpenMapTiles. Estas conexiones comunican datos técnicos, como la dirección
          IP, necesarios para recibir los archivos.
        </p>
        <p>
          Puedes consultar la{' '}
          <a href="https://developers.google.com/fonts/faq/privacy" target="_blank" rel="noreferrer">
            información de privacidad de Google Fonts
          </a>.
          Al abrir enlaces a fuentes oficiales o a GitHub, visitas sitios externos
          que tienen sus propias políticas de privacidad y cookies.
        </p>
      </section>
      <section>
        <h2>Cambios en esta información</h2>
        <p>
          Si se incorporan cookies u otras funciones de seguimiento, actualizaremos
          esta información antes de activarlas y solicitaremos consentimiento cuando
          corresponda. Consulta también los <Link to="/terms">términos y condiciones</Link>.
        </p>
      </section>
    </article>
  );
}
