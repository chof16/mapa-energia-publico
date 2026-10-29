# Fuentes, datos y límites de reutilización

La AGPL-3.0-only cubre el código original del proyecto. No cambia las condiciones
de las fuentes, documentos, marcas, geometrías o datos incorporados. Las bases
y descargas completas quedan fuera de Git; los manifiestos revisables y DDL SQL
sí forman parte de los archivos candidatos a publicación.

Cada descarga debe conservar su procedencia, atribución y condiciones de
reutilización. Antes de ejecutar los comandos de esta guía, verificar el endpoint
y los metadatos del organismo que publica los datos.

## Mercado: CNMC Data

Fuente: [energía y suministros](https://data.cnmc.es/energia/energia-electrica/energia-y-suministros),
con descubrimiento de datasets trimestrales mediante CKAN. Sus
[condiciones de uso](https://data.cnmc.es/condiciones-de-uso) establecen
CC BY-SA 4.0. Conservar licencia, fuente, revisión y fecha de actualización;
identificar las transformaciones y no sugerir respaldo de la CNMC.

Atribución: «Origen de los datos: Comisión Nacional de los Mercados y la Competencia».

La verificación histórica previa cubre 60 trimestres (2011T1–2025T4),
1.426.773 filas. No implica que el origen no tenga errores. Se conservan las
filas repetidas y ajustes negativos, con incidencias. `Consumidor Directo` y
`No Disponible` son categorías separadas; el denominador de cuotas por R2
incluye solo suministros con comercializadora registrada. Los nombres se
conservan por trimestre, sin inferir grupos ni fechas de alta/baja.

Estos datos no prueban cobertura geográfica de distribuidoras. Los censos de
la **sede** CNMC son una fuente diferente y pueden contener personas físicas
y direcciones privadas; no se importan ni publican en este proyecto.
No se les asigna la licencia de CNMC Data. SIPS no se utiliza.

### Otras fuentes de la CNMC

El proyecto también cita material de la CNMC ajeno a CNMC Data; por ejemplo,
el manifiesto utiliza una nota de prensa de `www.cnmc.es` para documentar la
relación entre UFD y Naturgy. No se debe extender la licencia de `data.cnmc.es`
a notas de prensa, registros, censos o documentos de otros portales de la CNMC.
Sus condiciones y el uso concreto de cada contenido requieren revisión propia.

La base combinada no está validada íntegramente para redistribución. Esta
revisión también afecta a los datos incluidos en JSON, catálogos y documentación
del repositorio: excluir SQLite de Git no resuelve por sí solo la publicación
de información procedente de esas fuentes. Una cuestión pendiente no equivale
a una prohibición confirmada; debe resolverse antes de publicar el contenido afectado.

## Gas: mapa de distribuidoras

La interfaz pública de gas muestra presencia provincial de distribuidoras y su procedencia
histórica. La web utiliza el mismo mapa y selección territorial que electricidad
en `/?sector=gas`; `/gas` es un acceso alternativo. La evolución minorista revisada
está en `/evolution?sector=gas` y el catálogo CUR en `/regulated-tariff?sector=gas`.
La preparación, API e interfaz de clientes, ventas y catálogo CUR se documentan
en [datos minoristas de gas](gas-retail-data.md):
usa evidencia privada, auditorías independientes y un esquema separado, todavía
sin revisión histórica completa ni autorización de redistribución. Compras y
censos electrónicos siguen fuera de alcance.

La API de redes mantiene los tres endpoints de `/v1/gas/distribution` descritos
abajo. El backend independiente `/v1/gas/retail` ofrece periodos, nombres
observados, series y revisiones, con valores exclusivamente de tablas revisadas;
`/v1/gas/reference-marketers` conserva evidencia CUR fechada. La ingesta explícita
`ingest-gas-retail` prepara sus tablas aditivas: no se instalan esquemas al arrancar.
La cobertura parcial y la reutilización pendiente siguen explícitas. No se
importan censos de gas ni se realizan refrescos minoristas automáticos.
El módulo eléctrico usa `/v1/electricity`; `/v1/market` conserva compatibilidad
para clientes antiguos. Su parámetro heredado `sector=gas` no consulta las
tablas de redes ni equivale al mapa de distribuidoras.

### Presencia provincial histórica

El [expediente IS/DE/007/20](https://www.cnmc.es/expedientes/isde00720-0),
publicado el 29/07/2020, incluye un
[anexo de municipios con redes de distribución](https://www.cnmc.es/sites/default/files/3085926.xlsx).
Aunque el informe corresponde al año 2019, el anexo declara **junio de 2019**
y redes de gas natural de presión **menor o igual a 4 bar**. No representa la red
actual ni todas las presiones, y no incluye GLP.

La importación local comprobada conserva 1.993 filas fuente, 18 denominaciones
observadas de distribuidoras y 48 provincias. La suma es 7.957.923 puntos de
suministro: se contrastan los subtotales provinciales y autonómicos y el total
nacional. Los subtotales se excluyen de las observaciones para no duplicarlos.
Se conserva el identificador de fila original y se admiten observaciones repetidas.
Las provincias `35`, `38`, `51` y `52` quedan sin evidencia en esta fuente;
esto **no prueba ausencia de red**.

El anexo no contiene códigos municipales INE. Se vinculan únicamente sus
etiquetas provinciales mediante una correspondencia exacta revisada a códigos
INE de dos cifras. Los nombres municipales permanecen como observaciones de
fuente: no se hacen uniones aproximadas ni se colorean municipios. La API suma
explícitamente los puntos por provincia y denominación observada, y cuenta filas
fuente, no municipios únicos. No se equiparan denominaciones históricas con
SIFCO, grupos actuales o comercializadoras. La presencia en parte de una provincia
no delimita redes, acredita exclusividad ni comprueba suministro en un domicilio.

| Endpoint | Contrato |
| --- | --- |
| `/v1/gas/distribution/provinces` | Provincias documentadas, número de denominaciones, filas y puntos de suministro |
| `/v1/gas/distribution/provinces/{code}` | Distribuidoras observadas en la provincia; lista vacía e incompleta significa desconocido |
| `/v1/gas/distribution/revisions` | Cargas conservadas, fecha del dato, publicación, hash y procedencia |

Los tres aceptan `limit` (50 por defecto, máximo 100), `offset` (0–10.000) y
`load_id`. La presencia usa la carga más reciente cuando falta el selector;
`revisions` permite descubrir todas las cargas conservadas. Las respuestas de
presencia declaran `sector=gas`, `scope=documented_provincial_presence` y
`complete=false`. Los nombres y recuentos pertenecen al mes indicado en `source.period`.
Los puntos de suministro describen las redes de las distribuidoras de esa fuente,
no clientes ni cuotas de comercializadoras.

```sh
uv run --package electricity-map-ingestion ingest-gas-distribution --database datos/mapa-v2.sqlite
uv run --all-packages python -m scripts.verify_gas_distribution --database datos/mapa-v2.sqlite
```

El primer comando reutiliza una descarga local o descarga el anexo a
`datos/raw/gas-distribution/`, ignorado por Git. También acepta `--xlsx /ruta/anexo.xlsx`.
Solo se admite el SHA-256 revisado
`d9ea1fc4783c916a849c88271831cac41ab9ea192e274207ff56d9df99e3b87d`.
Una revisión diferente exige revisar fuente y contrato. Se validan tamaño, firma
ZIP, expansión, miembros, XML, hoja, dimensiones, cabeceras, tipos, campos y
subtotales antes de archivar o escribir la base. No se ejecutan fórmulas ni macros.
El DDL `sql/gas_distribution_v1.sql` se instala explícitamente en una transacción
con la carga; no hay migración al iniciar la API. Las nuevas tablas
`gas_network_loads` y `gas_network_rows` conservan revisiones y no modifican
electricidad. No hay refresco automático del anexo.

**Condiciones de reutilización pendientes de aclaración para publicar el conjunto.**
El anexo pertenece a `www.cnmc.es`, no al portal CNMC Data; no se le asigna
CC BY-SA. La procedencia expone `reuse_status=review_pending`. La importación y
verificación local no autorizan redistribuir el archivo o una base completa;
la fuente original y las bases permanecen fuera de Git. Tampoco se han copiado
el mapa del comparador comercial ni inventarios de empresas con condiciones
restrictivas. Quedan pendientes fuentes territoriales más recientes, cruces
municipales verificables y la revisión de reutilización antes de publicar datos.

## Distribución provincial

`apps/api/src/electricity_map_api/distribution/claims.json` conserva identidades,
grupos y decisiones con fuente, motivo y fecha. La API sirve solo `accepted`;
`rejected` no prueba ausencia y `superseded` permite retirar sin borrar historia.
La instantánea revisada contiene 59 afirmaciones aceptadas, cuatro rechazadas
y 48 provincias con evidencia; `09`, `12`, `35`, `47` permanecen desconocidas.
Todas conservan `complete=false`. No demuestra cobertura de todos los municipios
ni exclusividad. El catálogo COR es independiente.

La [revisión provincial](../apps/api/distribution-evidence-review-2026-10-07.md)
documenta la evidencia. Las síntesis derivadas del BOE conservan la atribución
«Basado en datos de la Agencia Estatal Boletín Oficial del Estado» y se distinguen
del documento oficial, según su [aviso legal](https://www.boe.es/informacion/aviso_legal/).

La revisión previa dejó pendientes las condiciones de **BOCYL, BOME y las
afirmaciones procedentes de Endesa** para redistribuir el conjunto completo.
No declarar el manifiesto ni esa instantánea íntegra como AGPL o CC BY-SA por
el hecho de publicar el código. Antes de publicarlos, confirmar esas condiciones
o sustituir/retirar las afirmaciones afectadas conservando los motivos.
Los enlaces y los breves resúmenes de hechos no equivalen a una licencia de
los documentos originales; no se incluyen copias de mapas, imágenes o anexos.

## Cartografía

Fuente geométrica: [IGN API Features, unidades administrativas](https://api-features.ign.es/collections/administrativeunit).
Cruce exacto con la relación oficial [INE de municipios y códigos](https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736177031&idp=1254734710990).
Conservar licencia y fecha de cada descarga; consultar la
[política de datos del IGN](https://www.ign.es/web/ign/portal/politica-datos).
La atribución IGN/CNIG debe permanecer visible y acompañar los archivos cartográficos.

La referencia 2026 valida 8.132 códigos municipales INE. Las unidades IGN sin
correspondencia se conservan como auxiliares, sin asignar municipios por nombre
o aproximación. El catálogo navegable incluye además 52 provincias y 19 CCAA.
Los límites son una instantánea actual, no una reconstrucción histórica.
PMTiles y etiquetas deben generarse y publicarse juntos.

## Preparar datos locales

No es necesario descargar datos reales para ejecutar los tests. Para una
instalación con datos, desde la raíz y tras instalar las dependencias:

Los comandos de electricidad se llaman `ingest-cnmc-electricity` y
`refresh-cnmc-electricity`; sustituyen a `ingest-cnmc-market` y
`refresh-cnmc-market`. Para el mapa de gas se usa `ingest-gas-distribution`.
Todos pertenecen al mismo paquete de ingestión y pueden escribir en la misma
base de datos; el exportador general incluye todas sus tablas.

```sh
uv run --package electricity-map-ingestion ingest-cnmc-electricity --database datos/mapa-v2.sqlite
uv run --package electricity-map-api build-distribution-database --database datos/mapa-v2.sqlite
```

La primera orden descubre y descarga el mercado. `--cache-root datos/raw`
reutiliza una caché verificada si ya existe. La segunda carga el manifiesto
de distribución localmente; no es una aprobación para redistribuir sus fuentes.
Para actualizar mercado sobre la misma SQLite:

```sh
uv run --package electricity-map-ingestion refresh-cnmc-electricity --database datos/mapa-v2.sqlite
```

El refresco prepara solo trimestres nuevos/revisados y publica en una transacción
WAL, conserva distribución y revierte el lote si falla. No elimina ni deduplica
filas por aproximación. La API consulta vistas normalizadas `*_view`; el DDL
se mantiene en `packages/ingestion/src/electricity_map_ingestion/sql/electricity_v2.sql`.

### Generar la cartografía local

La UI usa un archivo PMTiles para los límites y un GeoJSON para las etiquetas.
Son recursos estáticos servidos por Vite, independientes de la base SQLite y de
la API. No se incluyen en el clon ni se descargan al arrancar la web.

Obtener de la [relación oficial INE](https://www.ine.es/dyngs/INEbase/operacion.htm?c=Estadistica_C&cid=1254736177031&idp=1254734710990)
el XLSX de municipios de 2026 y guardarlo como `datos/ine/municipios-2026.xlsx`,
conservando sus metadatos. También se admite un CSV UTF-8 con `CODAUTO`, `CPRO`,
`CMUN`, `NOMBRE`, manteniendo ceros. La canalización actual está validada contra
esa referencia; otra referencia requiere revisar el cruce completo.

Instalar `tippecanoe` por separado y comprobar que está en el PATH. Después,
desde la raíz del repositorio:

```sh
tippecanoe --version
uv run --package electricity-map-pipeline build-map --ine-csv datos/ine/municipios-2026.xlsx
```

El argumento se llama `--ine-csv` por compatibilidad y admite también XLSX.
La descarga completa del IGN y la generación pueden tardar; requieren conexión
y espacio local. Se reutiliza una caché temporal del IGN. Al terminar deben existir:

```text
apps/web/public/data/administrativo.pmtiles
apps/web/public/data/administrativo.etiquetas.geojson
```

Con `MAPA_MAP_ASSETS_DIR=public` y `VITE_ADMIN_PMTILES_URL` y
`VITE_ADMIN_LABELS_URL` vacías, arrancar Vite como indica el README. El navegador
los solicita a `/data/administrativo.pmtiles` y
`/data/administrativo.etiquetas.geojson`. Si esas peticiones devuelven 404 o HTML,
comprobar la ubicación de los archivos y reiniciar Vite tras cambiar su entorno.
Para usar una carpeta alternativa, `MAPA_MAP_ASSETS_DIR` debe apuntar al directorio
que **contiene** `data/`, no al propio `data/`. Usar una ruta absoluta evita
ambigüedades. Nunca mezclar PMTiles y etiquetas de generaciones distintas.

Las cuotas y la distribución necesitan además la SQLite y la API anteriores.
Los fondos y fuentes tipográficas externos pueden seguir requiriendo conexión;
esta configuración no constituye un modo sin conexión.

No subir datos reales a Git. La auditoría de solapes de unidades auxiliares sigue
siendo una comprobación pendiente; no deducir cobertura a partir de ellas.

### Exportar la base local

Para generar una copia y un volcado SQL verificados de la base local:

```sh
uv run --all-packages python -m scripts.export_database --database datos/mapa-v2.sqlite
```

La salida permanece en `datos/exports/`, fuera de Git. Esta herramienta no conecta
con servicios remotos, no publica los datos ni cambia sus condiciones de reutilización.
Comprueba consistencia técnica, pero no filtra información privada ni determina
derechos de redistribución. Su salida no es automáticamente un paquete publicable.

## Descargas preparadas: estado y alcance

No hay todavía una descarga preparada. La primera descarga prevista contiene
solo cartografía: PMTiles y etiquetas de la misma generación, acompañados de
versión, fecha, tamaños, hashes SHA-256, procedencia y condiciones de reutilización.
Se preparan y revisan antes de subirlos; los enlaces se documentan una vez
verificados. La configuración de cuentas y subida queda fuera de esta guía pública.

Una descarga de SQLite sería un recurso distinto y opcional para evitar la
preparación local de datos energéticos. El formato SQLite o SQL no determina si
su contenido se puede publicar. Antes de ofrecer esa descarga hay que revisar
las fuentes y el contenido del conjunto exacto, incluidas las fuentes CNMC ajenas
a CNMC Data, y preparar una copia limitada a los datos aprobados. Por ahora no
se ofrece la base combinada ni su volcado SQL.

Los scripts permiten reproducir y mantener los datos: inicialización, migración
de bases antiguas y exportación local. No son necesarios para consultar una
instantánea ya preparada y compatible, y no sustituyen la revisión de fuentes.
