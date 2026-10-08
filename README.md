# Mapa de energía de España

Mapa interactivo de distribuidoras eléctricas, cuotas autonómicas de
comercializadoras y evolución del mercado con datos de fuentes oficiales.
Proyecto independiente: las fuentes citadas no avalan la aplicación.

## Funcionalidades

- Navegación por comunidad, provincia y municipio, incluidas Canarias, Baleares,
  Ceuta y Melilla.
- Presencia provincial documentada de distribuidoras, con fuentes y confianza.
- Cuotas autonómicas, reproducción por trimestre y comparación de hasta cuatro
  comercializadoras en gráficos o tablas.
- Catálogo independiente de comercializadoras de referencia (tarifa regulada).
- API de lectura documentada en `/docs` y `/openapi.json`.
- Pie común con GitHub, declaración de independencia y páginas de cookies
  (`/cookies`) y términos y condiciones (`/terms`).

La cobertura de distribuidoras es incompleta y no identifica la red de cada
domicilio. Los límites administrativos son una instantánea actual. No hay
cuotas municipales/provinciales, datos personales, ofertas comerciales ni gas.

## Arquitectura

| Directorio | Responsabilidad |
| --- | --- |
| `apps/web` | React, TypeScript, Vite y MapLibre |
| `apps/api` | FastAPI, Pydantic y SQLAlchemy |
| `packages/domain` | Reglas compartidas |
| `packages/ingestion` | CNMC Data y refrescos locales |
| `packages/map_pipeline` | Cartografía IGN/INE y PMTiles |
| `scripts` | Inicialización, migración y exportación de datos |

En local, FastAPI consulta una SQLite y Vite sirve la interfaz y cartografía.
La web consulta la API; nunca necesita credenciales de la base de datos.
La API es pública y no requiere claves ni tokens de acceso. En producción aplica
por defecto un límite de 30 solicitudes por IP cada 60 segundos. En desarrollo
no aplica cuotas. CORS está disponible en ambos entornos; desarrollo permite
`http://localhost:5174` y `http://127.0.0.1:5174` por defecto. Para cambiar los
orígenes locales, ajustar `MAPA_CORS_ORIGINS`. La UI usa el proxy de Vite cuando
`VITE_API_BASE_URL` está vacío.

Los scripts públicos son herramientas locales: `build_combined_database.py`
inicializa una base a partir de otra existente, `normalize_database.py` migra
instantáneas antiguas y `export_database.py` genera una copia SQLite y SQL
verificados. No acceden a cuentas ni despliegan servicios. Un clon nuevo puede
preparar sus datos con los comandos de la guía sin usar estas migraciones.

## Desarrollo

Usar Python y Node según `.python-version` y `.node-version`, `uv` y
`pnpm` (versión en `package.json`). Desde la raíz:

```sh
uv sync --locked --all-packages
pnpm install --frozen-lockfile
```

Copiar `.env.example` a `.env` y `apps/web/.env.example` a
`apps/web/.env.local`. Ajustar `MAPA_DATABASE` a una SQLite normalizada y
`MAPA_MAP_ASSETS_DIR` al directorio que contiene `data/administrativo.pmtiles`
y `data/administrativo.etiquetas.geojson`. Los datos y credenciales no están
incluidos en Git. Ver [preparación de datos](docs/data-sources.md).

### Preparar el mapa que muestra la UI

**Clonar e instalar dependencias no descarga el mapa.** Vite necesita estos dos
archivos de la misma generación:

```text
apps/web/public/data/administrativo.pmtiles
apps/web/public/data/administrativo.etiquetas.geojson
```

Para generarlos, seguir [cartografía local](docs/data-sources.md#generar-la-cartografía-local):
descargar la relación municipal INE de 2026, instalar `tippecanoe` y ejecutar
`build-map`. La herramienta descarga la geometría del IGN y crea ambos archivos.
Dejar `MAPA_MAP_ASSETS_DIR=public` y las dos variables `VITE_ADMIN_*` vacías.
No hacen falta cuentas de alojamiento para servirlos con Vite.

La cartografía y los datos de energía se preparan por separado: generar el mapa
no crea la SQLite. Para probar cuotas, evolución y distribución, ejecutar también
los comandos de [datos locales](docs/data-sources.md#preparar-datos-locales) y
arrancar la API. Sin cartografía faltarán los límites y etiquetas propios; sin API
o base de datos las consultas energéticas mostrarán errores.

Todavía no hay una descarga preparada de los dos archivos cartográficos. No se
incluyen en Git; por ahora cada instalación debe generarlos o usar una copia de
la misma generación, conservando su atribución.

### Arrancar la aplicación

Ejecutar en dos terminales desde la raíz:

```sh
ENV=development uv run --env-file .env --package electricity-map-api uvicorn electricity_map_api.main:app --reload --host 127.0.0.1 --port 8001
```

```sh
pnpm --dir apps/web dev --host 127.0.0.1 --port 5174 --strictPort
```

Abrir `http://127.0.0.1:5174`. Sin base configurada las rutas de datos responden
503; `/healthz` solo indica que el proceso está vivo. Los tests usan datos
sintéticos y no requieren cuentas de proveedores ni descargas reales.

### Caché local opcional con Redis

La API puede compartir las respuestas de mercado y distribución mediante Redis.
Sin `MAPA_REDIS_URL`, consulta SQLite directamente. Para probar la caché con Docker:

```sh
docker run --rm --name mapa-redis -p 127.0.0.1:6379:6379 redis:7-alpine redis-server --save "" --appendonly no --maxmemory 64mb --maxmemory-policy allkeys-lru
```

Configurar en el `.env` local y reiniciar la API:

```dotenv
MAPA_REDIS_URL=redis://127.0.0.1:6379/0
MAPA_CACHE_TTL_SECONDS=300
```

La caché distingue base de datos, endpoint, comercializadora y todos los filtros.
Cada respuesta conserva juntos datos y metadatos y caduca después de cinco minutos
por defecto; una revisión puede tardar ese intervalo en aparecer. No se guardan
errores. La cabecera `X-Cache` indica `HIT`, `MISS` o `BYPASS`. Un `HIT` evita abrir
una conexión a la base. Si Redis falla, la API consulta la base con el límite de
solicitudes habitual y deja de intentar Redis durante 30 segundos.

La URL de Redis puede contener una contraseña: mantenerla en `.env`, nunca en
variables `VITE_*`. Redis no cambia el límite por IP, que sigue requiriendo una
única instancia y proceso. Las consultas existentes de la web no reintentan
automáticamente; el valor global para consultas que no lo especifiquen es de
dos reintentos adicionales al intento inicial.

Con Redis local activo, ejecutar su prueba de integración:

```sh
TEST_REDIS_URL=redis://127.0.0.1:6379/0 uv run --all-packages pytest apps/api/tests/test_cache.py
```

CI levanta su propio Redis temporal para esta prueba; no usa servicios ni secretos
externos. Sin `TEST_REDIS_URL`, solo se omite la prueba que requiere un servidor real.

## Comprobaciones

GitHub Actions ejecuta los tests de Python y de la web, Ruff y el build con
comprobación de tipos en cada pull request hacia `main` y cada push a esa rama.
Para ejecutar las mismas comprobaciones localmente:

```sh
uv run --all-packages pytest
uv run ruff check .
uv run ruff format --check .
pnpm --dir apps/web test
pnpm --dir apps/web build
```

El build incluye comprobación de tipos. Para previsualizarlo en local:

```sh
pnpm --dir apps/web preview --host 127.0.0.1 --port 4173
```

Con `VITE_API_BASE_URL` vacío y la API en marcha, Preview usa el mismo proxy
`/v1` de la configuración local: [Vite hereda `server.proxy`](https://vite.dev/config/preview-options.html#preview-proxy).
Si se compila con una URL explícita de API, añadir el origen de Preview
(`http://127.0.0.1:4173` o `http://localhost:4173`) a `MAPA_CORS_ORIGINS`
y reiniciar la API. Con el proxy no hace falta ese ajuste.
Los recursos generados y la configuración personal quedan fuera del repositorio.

## Datos y licencias

Los datos originales proceden de IGN/CNIG, INE, CNMC y las demás fuentes
citadas en [la guía de datos](docs/data-sources.md).

Copyright (C) 2026 Javier Jimenez y colaboradores.
El código original se distribuye bajo **AGPL-3.0-only**, sin garantía;
ver [LICENSE](LICENSE). Las dependencias mantienen sus licencias.
El repositorio de código fuente es
[chof16/mapa-energia-publico](https://github.com/chof16/mapa-energia-publico).

La licencia del código no cambia los derechos de los datos, documentos,
cartografía o marcas de terceros. CNMC Data y sus derivados conservan
CC BY-SA 4.0 y su atribución. La evidencia de distribución tiene condiciones
por fuente: **no se ofrece el conjunto completo bajo una licencia uniforme**.
También se utiliza material de la CNMC ajeno a CNMC Data; no se le aplica
automáticamente esa licencia. La base combinada y su SQL no están validados
para redistribución. La descarga cartográfica prevista es un recurso separado;
ver [estado de las descargas](docs/data-sources.md#descargas-preparadas-estado-y-alcance).
Consultar [fuentes y límites de reutilización](docs/data-sources.md).

La referencia verificada previa a la publicación abarca 2011T1–2025T4 y
48/52 provincias con evidencia positiva. Los refrescos programados siguen
pendientes; arrancar la API no descarga ni actualiza datos automáticamente.

Para contribuir, seguir [CONTRIBUTING.md](CONTRIBUTING.md): crear un fork,
trabajar en una rama y abrir una pull request hacia `main`. Las convenciones
del proyecto están en [AGENTS.md](AGENTS.md). Documentar fuentes y limitaciones,
acompañar cambios de comportamiento con las pruebas pertinentes y no incorporar
datos privados ni secretos.
