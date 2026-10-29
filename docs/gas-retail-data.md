# Preparación de datos minoristas de gas

La preparación de clientes y ventas de gas es independiente de la electricidad
y de la presencia de redes. Su API separada publica únicamente valores de tablas
revisadas y mantiene la cobertura pendiente explícita. La web ofrece evolución
y catálogo CUR separados del mapa de redes, mediante la navegación compartida.
Los informes trimestrales de CNMC/CNE y el catálogo de comercializadores de
último recurso tienen condiciones propias: no heredan la licencia de CNMC Data.
Las descargas, el OCR, las observaciones, los catálogos y los manifiestos de
evidencia se mantienen fuera de Git, con `reuse_status=review_pending`.

El índice de referencia es el de
[informes de supervisión del mercado minorista](https://www.cnmc.es/sectores-que-regulamos/energia/informes-supervision-mercado-minorista).
Un enlace o un informe descargado no acredita que existan valores utilizables.
La auditoría reserva dos estados independientes para cada uno de los 90 periodos
entre 2003T4 y 2026T1: clientes y ventas. La preparación histórica sigue incompleta.

## Contrato de evidencia

El JSON de entrada se valida con los modelos de
`packages/ingestion/src/electricity_map_ingestion/gas_retail.py`. Incluye fuentes,
entidades internas, correspondencias literales por fuente, auditorías,
observaciones mensuales y catálogo CUR independiente. No se admiten campos
desconocidos, claves repetidas, profundidad excesiva ni más de 64 MB de JSON.
Cada archivo fuente exige tamaño, formato permitido, firma y SHA-256 comprobados.
El importador consume transcripciones revisadas; no ejecuta decodificadores PDF.
Las notas de observación admiten hasta 4.000 caracteres para conservar completas
las explicaciones de contradicciones internas; los demás textos mantienen sus
límites y el manifiesto conserva el límite total de bytes.

La versión 2 conserva además auditorías por fuente, trimestre y métrica,
las celdas cuyo mes no se puede identificar, la unidad original y el estado
de revisión de cada celda, y las decisiones e incidencias del paquete CSV.
Los consumidores directos y las entidades sin clasificación se representan como
`direct_consumer` y `unknown`; no se convierten en comercializadoras.
Un mismo nombre impreso puede designar un grupo y una empresa en tablas distintas:
la correspondencia incluye fuente, nombre e identidad, sin deduplicar sus celdas.

Antes de transcribir un PDF, validar bytes, firma y terminación, y obtener
metadatos con límites de memoria, CPU, tiempo y salida. Limitar páginas y
dimensiones antes de extraer texto o renderizar. No eludir restricciones de
copia. Las tablas en imagen requieren OCR y contraste visual; los resultados
OCR son candidatos, nunca valores aprobados automáticamente.

Estados de auditoría:

| Estado | Significado |
| --- | --- |
| `not_reviewed` | No se ha revisado la fuente de esa métrica |
| `located` | Informe localizado, sin revisión de valores |
| `partial` | Revisión parcial; puede haber filas transcritas y otras pendientes |
| `reviewed` | Tabla y valores contrastados, con alcance explícito |
| `unavailable` | La revisión no encuentra la tabla requerida en esa fuente |
| `source_error` | Defecto identificado en la fuente; no fabricar un dato sustitutivo |

`partial` no equivale a `reviewed`. Un consumidor debe consultar la auditoría
junto con cada serie y evitar publicar correspondencias provisionales como
identidades verificadas. La ausencia de filas no equivale a cero. Revisar una
tabla numérica tampoco acredita continuidad societaria: una correspondencia
`source_local_identity` conserva un ID limitado a su fuente. Solo las decisiones
`reviewed_identity` documentadas enlazan nombres entre informes.

`gas_retail_source_audits` conserva las revisiones alternativas y distingue
`table_review_status` de `retailer_coverage`. La tabla anterior
`gas_retail_audits` mantiene 180 resúmenes conservadores: no marca un periodo como
revisado si alguna fuente o cobertura está pendiente. Hasta adaptar el backend
a auditorías por fuente, esos resúmenes pueden ocultar una tabla revisada cuando
coexiste con otra parcial; no autorizan publicar esta última.

Cada observación conserva mes, nombre observado, página PDF (base 1), fila,
etiqueta de tabla, unidad, cadena original y nota de revisión. Los estados
`exact`, `zero`, `missing`, `suppressed`, `source_error` y `bounded` son distintos.
Los valores exactos se almacenan como texto decimal para evitar redondeos binarios;
`<50` tiene valor nulo y límite superior exclusivo 50, nunca 0, 25 o 49.

Los clientes trimestrales usan exclusivamente marzo, junio, septiembre o diciembre.
Las ventas requieren exactamente los tres meses del trimestre, de la misma
revisión, identidad interna, alcance y unidad. No completar huecos desde otro
informe. Las filas repetidas se conservan; un mes repetido relevante bloquea
el agregado como `source_error`. Los límites acotados producen otro límite,
no una venta exacta. No sumar clientes ni sumar grupos y sus empresas.

`liberalised`, `whole_market` y `regulated` describen el mercado, no la geografía.
La geografía debe leerse en la fuente: algunos informes antiguos se limitan a la
zona peninsular. No convertir esos ámbitos en cobertura nacional, provincial o
municipal. Los IDs `gas-*` son internos. Las correspondencias de identidad
revisadas pueden vincular nombres de varios informes a una misma empresa;
cada observación sigue perteneciendo a su fuente. Las coincidencias de texto
por sí solas no acreditan continuidad histórica, grupos actuales ni R2.

Las excepciones incluyen el tercer mes mal rotulado como `Juio` en ventas de
2007T2, ventas solo por grupos en 2010T3, la tabla de clientes repetida bajo el
título de ventas en 2014T3 y filas repetidas de PETRONAVARRA en 2014T4. No asignar
un mes al rótulo defectuoso ni fabricar ventas a partir de clientes. Las
continuaciones de 2019T4–2020T3 y las tablas de imagen pendientes de contraste
siguen siendo parciales. Los defectos y la revisión restante deben conservarse
en la auditoría de la revisión correspondiente.

El catálogo CUR conserva denominación, designación específica de gas, fuente y
fecha de evidencia. Una fecha de consulta no es una fecha de alta legal.
No unir automáticamente nombres abreviados de tablas con el catálogo ni reutilizar
el COR eléctrico. No contiene precios, contactos ni datos de censos electrónicos.

## API de lectura

Las rutas siguientes se documentan también en `/docs` y `/openapi.json`.
Requieren instalar e importar explícitamente las tablas en la base configurada
para la API. No hay DDL, descarga ni importación durante el arranque.

| Ruta GET | Contenido y filtros |
| --- | --- |
| `/v1/gas/retail/periods` | Auditoría por trimestre y métrica; `metric`, `scope` y `period` opcional |
| `/v1/gas/retail/marketers` | Empresas canónicas revisadas con evidencia o diagnóstico admisible; una por empresa, mismos filtros y búsqueda por nombre o alias |
| `/v1/gas/retail/series/{marketer_id}` | Puntos trimestrales con auditoría, registros, procedencia mensual y denominador; `metric`, `scope`, `start_period`, `end_period` |
| `/v1/gas/retail/revisions` | Revisiones inmutables, fechas, recuentos de auditoría y problemas de cobertura |
| `/v1/gas/reference-marketers` | Catálogo CUR independiente con variantes observadas y fechas de evidencia |

Todas admiten `load_id` opcional, un SHA-256 de 64 caracteres hexadecimales.
Sin él se usa la última carga importada; conviene conservarlo para reproducir una
consulta. Las listas usan `limit=50`, máximo 100, y `offset=0`, máximo 10.000.
La serie usa `limit=120`, máximo 120 trimestres, y el mismo límite de desplazamiento;
los límites temporales son inclusivos y usan `AAAA Tn` sin espacio, por ejemplo
`2025T1`. El orden de periodos y series es ascendente. `metric` vale `clients`
(predeterminado) o `sales`; `scope` vale `whole_market` (predeterminado),
`liberalised` o `regulated`. No se admiten provincias, comunidades, municipios,
filtros eléctricos ni parámetros desconocidos: se responde 422.

`periods` conserva las auditorías pendientes, aunque no haya valores. Su recuento
de comercializadores revisados cuenta empresas canónicas distintas en el ámbito
consultado y con evidencia admisible de su fuente.
En v2 cada periodo incluye `source_audits`, con estado, revisión de tabla,
cobertura minorista, geografía, páginas y nota de cada fuente por separado.
El campo `audit` sigue siendo el resumen conservador: puede indicar `partial`
si una fuente es parcial aunque otra esté revisada y aporte valores válidos.
En revisiones antiguas `source_audits=[]` y se aplica la auditoría del periodo.
`marketers`
pagina empresas canónicas por `marketer_id`: tanto `total` como los desplazamientos
cuentan empresas distintas, no apariciones ni IDs locales por informe. Las
correspondencias revisadas de una misma empresa enlazan todos sus informes;
sus nombres observados y procedencia permanecen separados. `company_name` es la etiqueta
canónica; `observed_name` y `source` conservan una observación revisada del último
trimestre que cumple los filtros, con desempate estable por ID de correspondencia.
La búsqueda literal, sin distinguir mayúsculas, admite el nombre canónico y los
alias históricos revisados, incluso si el alias pertenece a otro periodo, métrica
o ámbito. La empresa debe seguir cumpliendo los filtros de elegibilidad y la
búsqueda no cambia su observación representativa. Los alias solo transcritos en
tablas parciales no se usan para buscar. Se excluyen grupos, Resto, totales,
consumidores directos y entidades de tipo desconocido, incluso si comparten
un nombre impreso con una comercializadora.
Los IDs deben obtenerse de la respuesta y conservarse como clave de selección,
nunca derivarse del nombre ni de R2. Solo las correspondencias de identidad
revisadas en los datos permiten continuidad entre informes; la API no une nombres
parecidos ni consolida empresas petrolíferas, grupos y comercializadores de gas.

Cada comercializadora y la raíz de su serie incluyen `identity_status` y
`identity_review_note`. En v2 solo `reviewed_identity` permite entrar en el
catálogo público y consultar una serie de empresa. `source_local_identity`
se conserva como evidencia interna de una fuente: no es una opción del selector,
no participa en su búsqueda o paginación y una consulta directa de serie por ese
ID devuelve 404. Las decisiones de continuidad pertenecen a la revisión de datos,
nunca a una unión aproximada de nombres en la API o la web. Los totales explícitos
de una fuente siguen disponibles como denominadores sin convertirse en empresas.

`legacy_unspecified` identifica snapshots v1 anteriores al estado explícito de
identidad. Esas revisiones conservan su contrato histórico al seleccionarlas
mediante `load_id`; no se utilizan para reconstruir automáticamente la identidad
canónica actual. `reviewed_identity` tampoco acredita un registro exhaustivo de
todas las empresas. Un enlace de evolución usa el ID canónico de la revisión elegida.

Cada revisión incluye `coverage` con recuentos por métrica y estado de auditoría,
enlaces `audits_url` a los periodos de esa misma revisión y `issue_count` con el
número de auditorías no revisadas. `issues` conserva los primeros diez problemas
en orden de trimestre/métrica, con nota y enlace `audit_url`; `issues_truncated`
indica si hay más. Los enlaces de cobertura permiten recorrer todos los periodos
con la paginación habitual, sin cargar ni publicar el manifiesto privado.

La serie del ID estable incluye `company_name` y devuelve una entrada por
trimestre auditado, con todos sus registros revisados entre fuentes y nombres
observados, sin sumar informes superpuestos ni mezclar ámbitos. `availability`:
`reviewed` si existen registros revisados para ese comercializador y ámbito,
`unreviewed` si la revisión de celdas sigue pendiente o el periodo pendiente no
tiene registros, y `unavailable` si solo hay diagnósticos de error o no existe
una observación publicable en una auditoría no disponible o defectuosa. `records=[]`
no implica cero. Los trimestres fuera de la matriz de evidencia no se inventan.
Cada registro y su denominador conservan `status` numérico, `review_status`
(`reviewed`, `partial` o `source_error`) y `source_audit` para su fuente, periodo
y métrica. `source_audit=null` identifica el contrato antiguo. En v2 un valor
requiere fuente y tabla revisadas, cobertura minorista revisada y todas las
celdas contribuyentes revisadas. Una alternativa parcial no aporta registros
numéricos, aunque el resumen global diga revisado; tampoco bloquea otra fuente
que sí cumpla todos los requisitos. No se elige ni suma una alternativa por defecto.

Una celda contribuyente parcial bloquea el agregado, su valor/límite original y
la cuota. Su ID queda en `withheld_observation_ids`, pero no se publican su literal
ni sus números; el registro indica `review_status=partial` y `status=missing`.
La procedencia de las celdas revisadas puede conservarse. Un error de fuente se
devuelve únicamente como diagnóstico con valores trimestrales nulos. El selector
puede incluir su identidad para inspeccionarlo; esto no acredita valores exactos.
Un ID sin evidencia minorista revisada o diagnóstico admisible responde 404.

Los valores y cuotas JSON son cadenas decimales para conservar precisión.
Clientes usa el último mes; ventas requiere los tres. Ventas se normaliza a
`MWh` (GWh × 1.000; kWh × 0,001), manteniendo `original_unit`, `original_value`,
`original_upper_bound` y las unidades mensuales. Un límite superior es exclusivo:
`bounded` conserva `value=null`, `upper_bound` y `upper_bound_exclusive=true`.
`missing_months`, `input_statuses` y `observations` conservan los huecos, estados,
nombres, valores originales, filas, páginas PDF y notas de correspondencia.
La fuente aporta URL, título, organismo, publicación si consta, consulta,
SHA-256 y notas geográficas; la revisión superior identifica la carga común.

Cada observación mensual añade `original_unit` literal (por ejemplo, `Número de
Clientes`), `review_status` y `publication_status` (`reviewed` o `source_error`).
Un diagnóstico puede conservar su literal y estado original, pero sus campos
`value` y `upper_bound` son nulos si no están aprobados para publicación numérica.
No interpretar el literal como valor validado. La unidad original trimestral
mantiene su significado semántico y las unidades literales quedan en las celdas.

`unresolved_observations` conserva por separado las celdas sin mes asignable:
ID, correspondencia, nombre observado, trimestre, `month=null`, unidad original,
página, tabla, fila, literal y nota de revisión. Su estado es `source_error` y
valor/límite son nulos. No completar junio a partir de `Juio` ni sumar esas celdas
como meses válidos. En ventas el resultado sigue `missing` cuando falta un mes.
Las observaciones de clientes v2 referencian solo el mes final.

Para dibujar un punto v2 se comprueba su `source_audit` y `review_status`, no se
rechaza automáticamente por el resumen parcial del trimestre. Solo se dibujan
valores exactos o ceros con valor/cuota no nulo; las fuentes superpuestas deben
mostrarse separadas, sin elegir ni sumar una arbitrariamente. Las revisiones
antiguas mantienen la comprobación de auditoría del periodo.

`share` solo existe para valores `exact` o `zero` y un único total explícito
exacto positivo de la misma fuente, trimestre, métrica y ámbito. El denominador
incluye su identidad, unidad normalizada y procedencia. No se suman filas
superpuestas para construirlo. `denominator_status` distingue `matched`,
`missing`, `ambiguous`, `unavailable`, `zero` e `inconsistent` (numerador mayor
que el total). En estos últimos casos la cuota es nula; un numerador cero sobre
un denominador positivo sí produce cuota cero. Un numerador acotado o no
disponible tampoco produce cuota, aunque el denominador esté identificado.

El catálogo contiene cuatro entidades CUR en la evidencia preparada, cada una
con dos observaciones independientes: guía de gas CNMC de 14-11-2022 y página
oficial consultada el 29-10-2026. Se preservan denominaciones y variantes, la
designación `gas_cur`, las fechas, páginas y fuentes. La fecha de consulta de una
página sin fecha de publicación no se presenta como fecha legal de alta.
No hay precios ni asociación inferida con COR eléctricos o series estadísticas.

Las respuestas mantienen `complete=false`, `geographic_scope=source_defined` y
`reuse_status=review_pending`: ni una respuesta válida ni una tabla auditada
resuelven los derechos de reutilización. No redistribuir el conjunto de evidencia
ni la base combinada sin revisar sus condiciones. No se afirma comparabilidad
nacional histórica. Una revisión ausente devuelve 404; una base o esquema
ausente devuelve 503. Las revisiones vacías se enumeran como lista vacía.
Se comparten sesiones de solo lectura, caché opcional y límites de peticiones
con las otras APIs; una respuesta en caché también consume cuota.

## Interfaz web

`/evolution?sector=gas` empieza en **Clientes** y **Mercado completo**.
Clientes usa el último mes del trimestre; **Ventas (MWh)** requiere los tres meses.
Se puede elegir valor absoluto o cuota, gráfico o tabla, y acotar los trimestres.
No hay filtros territoriales ni mapa de comercializadoras de gas.

La selección utiliza los mismos desplegables de búsqueda y comparación que
electricidad. No hay formulario de búsqueda separado ni paginación visible:
el catálogo se carga con `limit=100` y se filtra al escribir en el
desplegable. Si supera una página de la API, se recorren páginas acotadas y
fijadas a la misma revisión para no ocultar empresas. La API pagina empresas
únicas, no documentos ni variantes. Una selección reúne la historia revisada de
la empresa entre informes mediante su ID canónico. Los IDs locales de observación
no son opciones del selector. El navegador no fusiona nombres; las correspondencias
se resuelven en los datos. Si empresas distintas tienen la misma etiqueta, se añade
su ID para distinguirlas. Se pueden comparar hasta cuatro empresas. Los nombres originales siguen accesibles
en la procedencia de cada trimestre. La búsqueda por alias históricos también
está disponible para consumidores directos de la API.

**Ámbito histórico del mercado** distingue mercado completo, liberalizado y
regulado; no representa geografía. Cambiar de ámbito o métrica limpia las
comercializadoras para evitar comparaciones incompatibles. Los filtros de serie,
presentación y selección se restauran al usar Atrás/Adelante. Cambiar
de página empieza en sus valores predeterminados; cambiar de sector permanece
en esa página y elimina los identificadores y filtros anteriores.
Los enlaces con IDs antiguos por documento limpian esa selección y piden elegir
la empresa. Una revisión fijada mediante `load_id` se indica expresamente; quitar
ese parámetro del enlace vuelve a la última revisión. Sin revisión fijada, la
interfaz comprueba novedades al recuperar el foco y cada minuto, sin botón manual.
La caché de empresas está versionada para no reutilizar catálogos documentales antiguos.

Los selectores principal y de comparación incluyen aclaraciones para distinguir
Plenitude de Eni España Comercializadora de Gas, y Cepsa Gas de Cepsa Comercial
Petróleo. Se conservan los nombres e IDs de la API. «Contexto actual de las empresas
seleccionadas», bajo el gráfico, recoge la fecha de consulta y enlaces oficiales.
Son notas informativas actuales: no describen la segmentación histórica de los
clientes, no unen series y no equiparan cambios de marca con fusiones legales.

El gráfico mantiene su altura al desplazar la página o mostrar el detalle de un
punto. El detalle aparece junto al punto y se ajusta a los bordes, sin un segundo
mensaje nativo al mantener el cursor. «Valores, notas y fuentes por trimestre»
conserva la procedencia bajo el gráfico. No se repiten los límites en párrafos
ni se muestran los paneles generales de lectura y auditoría. En móvil, los filtros
preceden al gráfico y la tabla; los dos límites trimestrales comparten fila.
Los botones compactos de gráfico y tabla usan iconos SVG con nombres accesibles
y estado seleccionado. Se mantiene visible la advertencia geográfica.
En pantallas estrechas, los márgenes del gráfico se reducen para aprovechar el
ancho, reservando espacio para las cifras del eje. La navegación compartida usa
«Evolución»; el título de la página conserva «Evolución de comercializadoras».
Los selectores de sector, métrica y dato reparten el ancho por igual entre sus
botones. En móvil, los enlaces de navegación se agrupan con separación uniforme.

La cobertura informa cuántos resúmenes trimestrales están revisados por métrica,
con el detalle independiente de cada fuente y celda. En la evidencia
anual importada, incluida la revisión de 2004T4 y 2006T3, hay 209 auditorías de
fuente y métrica, de las cuales 178 están revisadas tras completar 2004T1.
Los 180 resúmenes conservadores marcan 75 periodos revisados para clientes y 75 para ventas;
no equivalen a 90 series completas ni a identidades
históricas verificadas para todas las empresas.
Los periodos pendientes siguen como huecos. Los límites exclusivos, como `<50`,
se muestran en la tabla y en el detalle por trimestre, sin punto inventado en el gráfico. Ni los
huecos ni los límites se interpolan. Las cuotas sin un total válido explican su
ausencia. Varios registros para el mismo punto no se suman ni se dibujan como uno.

La revisión de 2004T1 documenta un defecto gráfico: dos rectángulos opacos por
página cubren texto existente. La inspección diagnóstica suprimió únicamente
esos rellenos en memoria, verificó que glifos y posiciones no cambiaron y cotejó
las 108 celdas visualmente. El PDF original permanece intacto; la procedencia
explica el método y conserva las discrepancias de los totales impresos.

La advertencia geográfica permanece visible: algunos informes antiguos son
peninsulares y no se presupone comparabilidad nacional histórica. Tampoco se
unen nombres parecidos por decisión del navegador. Solo las correspondencias
revisadas del backend enlazan una misma empresa entre fuentes. El identificador
del documento no es el identificador de la empresa; un cambio de informe no corta
una línea entre trimestres consecutivos revisados de la misma empresa, métrica y
ámbito. Las empresas distintas, grupos y cambios pendientes permanecen separados.
Los desplegables de fuentes conservan notas de auditoría, enlaces al PDF y páginas,
meses, celdas originales, unidades y procedencia del denominador. Las peticiones
de una vista usan una misma revisión; se puede fijar su `load_id` en el enlace.
Las celdas con mes sin resolver se muestran en la procedencia como defectos,
sin asignarles mes ni valor trimestral. Las celdas parciales permanecen ocultas;
se informa del número de observaciones retenidas. Los valores alternativos del
mismo trimestre se conservan separados en tabla y procedencia, sin punto agregado.

`/regulated-tariff?sector=gas` presenta las CUR de gas y explica la TUR, sin
precios. En la evidencia preparada hay cuatro entidades, cada una con dos
observaciones fechadas. Se muestran las variantes literales y sus fuentes;
la fecha de consulta no es una fecha legal de alta. No se relacionan automáticamente
con COR eléctricas, estadísticas, distribuidoras o coberturas territoriales.

Ambas vistas incluyen carga, reintento, error y ausencia de datos. Una API sin
las tablas importadas mostrará el estado correspondiente, sin inventar entradas.
La interfaz no completa la auditoría pendiente ni autoriza redistribuir la evidencia.

## Importación explícita y verificación local

Para una entrega de revisión anual, conservar sus originales y preparar un JSON
nuevo con el conversor reproducible:

```sh
uv run --package electricity-map-ingestion python -m electricity_map_ingestion.gas_retail_yearly --review-dir datos/raw/gas-retail/yearly-review --base-evidence datos/raw/gas-retail/base-evidence.json --sources-dir datos/raw/gas-retail/sources --output datos/raw/gas-retail/review-v2.json
```

La base aporta el inventario previo y el catálogo CUR independiente. El conversor
valida los 72 CSV anuales y cinco CSV comunes, tamaños, UTF-8, columnas, referencias,
unidades y recuentos; recalcula todos los trimestres y contrasta valores, límites,
meses ausentes y procedencia. Guarda hashes de entrada y rechaza una salida
existente. No ejecuta los scripts incluidos en una entrega externa.
El texto de revisión y sus resultados declarados no sustituyen esas comprobaciones.

Los IDs locales por documento del paquete anual son claves de extracción, no
empresas para el selector. Antes de importar, preparar un registro explícito de
identidades con `base_load_id` del JSON original, todas sus correspondencias y
referencias a fuente y página. Cada decisión canónica v2 exige una nota que
empiece por `reviewed_identity:` y explique su fundamento. El importador rechaza
los IDs de extracción `gas-cnmc-*` sin resolver; la reconciliación rechaza
decisiones sin admisión explícita, referencias inválidas, cambios de tipo y
uniones de filas coexistentes. Las decisiones completas quedan en
`gas_retail_review_records`, vinculadas a la revisión de origen.

Una identidad estadística revisada conserva el mismo ID entre informes. Los
PDF, nombres y celdas permanecen como procedencia; no crean nuevas empresas.
Los cambios sustantivos de denominación necesitan una correspondencia explícita;
no se deduce una fusión jurídica de un rótulo parecido. Esta revisión de identidad
es independiente de la admisión numérica de cada fuente y celda.

Las correcciones posteriores deben partir de la última evidencia auditada, no
del paquete de extracción inicial: así se conservan revisiones de celdas y tablas
realizadas después de la primera importación. Antes de importar una unión,
comprobar que solo cambian las correspondencias autorizadas, que no aparecen
filas coexistentes y que los resultados trimestrales mantienen cifras, estados,
alcances y fuentes. Guardar la revisión anterior y la decisión con sus referencias.

Para una normalización de muchas empresas, separar las propuestas documentadas,
las condicionadas a comprobar una abreviatura y las pendientes. La aprobación
del informe no aporta la prueba que falta en estas últimas: conservarlas sin
unir hasta resolver sus referencias. Suprimir puntuación o sufijos sirve para
encontrar candidatos, nunca para asignar automáticamente una identidad. Palabras
como «España», «Clientes» o «Generación» pueden distinguir sociedades distintas.

La entrega debe enumerar los IDs conservados y retirados de la nueva revisión,
mantener intactos los nombres observados y las decisiones anteriores, y comparar
todos los resultados trimestrales después de sustituir únicamente los IDs
autorizados. Comprobar la última carga tanto en la base revisada como en la de
previsualización antes de importar; verificar después integridad, reimportación
idempotente, búsquedas por alias y series a través de la API. Los IDs anteriores
permanecen en las revisiones históricas; no resolver enlaces antiguos mediante
uniones inventadas en el navegador. Las uniones de alias usan el esquema existente
de entidades y correspondencias y no exigen por sí solas migraciones SQL.

La capitalización visible se normaliza en el nombre canónico de la entidad,
mediante una lista explícita de cambios revisados que preserve las siglas y la
ortografía de las marcas. No aplicar una conversión automática a todos los
nombres extraídos: `observed_name`, el catálogo CUR fechado y los textos de fuente
conservan sus literales originales. Un cambio de presentación mantiene los IDs,
las correspondencias y las auditorías, genera una revisión nueva y exige regenerar
la exportación SQL. Verificar que su `load_id` coincide con las dos bases locales;
importar primero `schema.sql` y después `data.sql` del mismo paquete. Un export
histórico no incorpora correcciones realizadas en revisiones posteriores.

El contexto comercial mostrado junto a una empresa en el selector es explicativo
y fechado: no define el segmento histórico de sus clientes ni autoriza una unión
de series. Distinguir marca, matriz, filial y subtotal de grupo. Un cambio de marca
no acredita por sí solo un cambio de razón social; una razón social actual tampoco
sustituye los nombres originales de las observaciones.

```sh
uv run --package electricity-map-ingestion ingest-gas-retail --evidence datos/raw/gas-retail/review-v2.json --identities datos/raw/gas-retail/identity-registry.json --sources-dir datos/raw/gas-retail/sources --database datos/gas-retail.sqlite --dry-run
uv run --package electricity-map-ingestion ingest-gas-retail --evidence datos/raw/gas-retail/review-v2.json --identities datos/raw/gas-retail/identity-registry.json --sources-dir datos/raw/gas-retail/sources --database datos/gas-retail.sqlite
```

Si el JSON ya contiene las identidades canónicas resueltas, conservarlo junto a
los archivos originales en una carpeta ignorada, por ejemplo
`datos/raw/gas-retail/`, y ejecutar primero la validación:

```sh
uv run --package electricity-map-ingestion ingest-gas-retail --evidence datos/raw/gas-retail/evidence.json --sources-dir datos/raw/gas-retail/sources --database datos/gas-retail.sqlite --dry-run
uv run --package electricity-map-ingestion ingest-gas-retail --evidence datos/raw/gas-retail/evidence.json --sources-dir datos/raw/gas-retail/sources --database datos/gas-retail.sqlite
```

La segunda orden instala explícitamente el DDL aditivo
`sql/gas_retail_v1.sql` y escribe una transacción completa. También puede usar la
base normalizada existente: no modifica tablas de electricidad o redes.
Nunca se instala al arrancar la API. Se conserva cada revisión y se devuelve
su `load_id`, SHA-256 del JSON canónico validado. Reimportar el mismo contenido
verifica todas sus filas y no las duplica; una discrepancia se rechaza.

Las tablas son `gas_retail_loads`, `gas_retail_sources`, `gas_retail_entities`,
`gas_retail_mappings`, `gas_retail_audits`, `gas_retail_observations`,
`gas_retail_quarters` y `gas_retail_catalogue`. Las referencias incluyen `load_id`;
no mezclar cargas al consultar fuentes, correspondencias o resultados derivados.
`gas_retail_quarters` incluye estados de entrada, meses ausentes e IDs de las
observaciones utilizadas. Las revisiones declaran `complete=false`.

La versión 2 añade `gas_retail_source_audits`,
`gas_retail_unresolved_observations`, `gas_retail_observation_details` y
`gas_retail_review_records`. Las celdas sin mes no reciben uno inventado y no
completan ventas trimestrales. La procedencia de clientes identifica únicamente
el mes final utilizado. La unidad semántica `clients` y el encabezado original
se conservan por separado.

La importación migra transaccionalmente las restricciones antiguas de entidades
y correspondencias en SQLite. Conserva el contenido y los hashes de todas las
revisiones anteriores; un fallo revierte también el cambio de esquema. Sustituir
un borrador significa cargar una revisión nueva, sin mezclar sus filas ni eliminar
el historial necesario para explicar los cambios. La exportación PostgreSQL
incluye la adaptación explícita de restricciones en su archivo de esquema.

## Preparar PostgreSQL

El DDL es compatible con SQLite y PostgreSQL. El exportador no lee credenciales,
no conecta a servicios remotos y no modifica la base local. Requiere un `load_id`
explícito y comprueba integridad, claves foráneas y equivalencia de todas las
filas con el manifiesto guardado antes de preparar artefactos.

```sh
uv run --all-packages python -m scripts.export_gas_retail_postgres --database datos/gas-retail.sqlite --load-id "$GAS_RETAIL_LOAD_ID" --dry-run
uv run --all-packages python -m scripts.export_gas_retail_postgres --database datos/gas-retail.sqlite --load-id "$GAS_RETAIL_LOAD_ID" --output-dir datos/exports/gas-retail
```

La carpeta de salida debe ser nueva. Contiene `schema.sql`, `data.sql` y
`verification.json`. La instalación remota es un paso separado y explícito:
primero esquema, luego datos, mediante `psql -X -v ON_ERROR_STOP=1 -f` y una
conexión configurada privadamente. No introducir URLs ni secretos en ejemplos
públicos o argumentos registrados. No ejecutar estos pasos sin autorización.

`data.sql` es un script para `psql`: usa `COPY FROM STDIN` hacia tablas temporales,
inserta por conjuntos y contrasta todos los campos y recuentos antes del `COMMIT`.
No se debe enviar entero mediante un simple `execute()` de un controlador SQL.
Evita los viajes de red de una inserción y comprobación por fila. Los mensajes
de progreso por tabla se muestran incluso con `psql -q`; «Carga masiva confirmada»
solo aparece después del `COMMIT` correcto. El script activa `ON_ERROR_STOP`.

Los archivos usan transacciones y tiempo de bloqueo limitado; no contienen
borrados ni reemplazos de datos existentes.
La repetición es idempotente y una revisión conflictiva provoca rollback.
La fecha de primera importación del destino se conserva. La verificación técnica
no autoriza redistribución. Probar el SQL primero en PostgreSQL aislado.

Si se cancela `data.sql` antes del `COMMIT`, se revierte esa transacción completa;
el esquema instalado mediante `schema.sql` tiene su propia transacción y permanece.
Esperar a que el proceso anterior termine antes de reintentar. Exportaciones
antiguas conservan su formato original: generar una carpeta nueva para usar COPY.

## Pruebas

```sh
uv run --all-packages pytest packages/ingestion/tests/test_gas_retail.py
uv run --all-packages pytest packages/ingestion/tests/test_gas_retail_yearly.py
uv run --all-packages pytest apps/api/tests/gas/test_gas_retail_api.py
uv run ruff check .
uv run ruff format --check .
```

Las pruebas usan fuentes sintéticas y cubren agregación, estados, ámbitos,
correspondencias, revisiones, repetición, rollback, validación y exportación.
La prueba PostgreSQL requiere `TEST_POSTGRES_URL` de un servicio aislado local;
se omite si no está configurado. La paridad de API con PostgreSQL usa un esquema
temporal aislado, comprueba respuestas contra SQLite y prohíbe escrituras.
Nunca usar una base de producción para estas pruebas.
