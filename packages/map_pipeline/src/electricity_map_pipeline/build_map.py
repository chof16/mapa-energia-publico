#!/usr/bin/env python3
"""Download and build IGN administrative layers linked to INE codes."""

from __future__ import annotations

import argparse
import csv
import io
import json
import numbers
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime
from itertools import pairwise
from pathlib import Path
from typing import Any

ITEMS_URL = "https://api-features.ign.es/collections/administrativeunit/items"
USER_AGENT = "MapaElectricas/0.1 (preparacion cartografica; fuente IGN/CNIG)"
PAGE_LIMIT = 10
MAX_RESPONSE_BYTES = 40 * 1024 * 1024
MAX_INE_ROWS = 10_000
LAYERS = ("municipios", "provincias", "ccaa", "unidades_auxiliares")


class CartographyError(Exception):
    """Error de descarga o validación que debe detener la generación."""


class ResponseTooLargeError(CartographyError):
    """Pide reintentar el mismo offset con menos elementos."""


def read_ine_csv(ruta: Path) -> dict[str, dict[str, str]]:
    """Lee el CSV municipal INE exportado y valida sus claves."""
    try:
        contenido = ruta.read_bytes()
    except OSError as error:
        raise CartographyError(f"No se puede leer la relación INE: {ruta}") from error
    if not contenido or len(contenido) > 20 * 1024 * 1024:
        raise CartographyError("El CSV INE está vacío o supera el máximo de 20 MiB")
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CartographyError("El CSV INE debe estar codificado en UTF-8") from error
    muestra = texto[:8192]
    try:
        dialecto = csv.Sniffer().sniff(muestra, delimiters=";,\t")
    except csv.Error:
        dialecto = csv.excel
    return _read_ine_csv_rows(io.StringIO(texto), dialecto)


def read_ine_xlsx(ruta: Path) -> dict[str, dict[str, str]]:
    """Lee el XLSX oficial con límites de tamaño antes de analizar su XML."""
    try:
        contenido = ruta.read_bytes()
    except OSError as error:
        raise CartographyError(f"No se puede leer la relación INE: {ruta}") from error
    if not contenido or len(contenido) > 20 * 1024 * 1024:
        raise CartographyError("El XLSX INE está vacío o supera el máximo de 20 MiB")
    if not contenido.startswith(b"PK\x03\x04"):
        raise CartographyError("El fichero .xlsx no tiene la firma ZIP esperada")
    if not zipfile.is_zipfile(io.BytesIO(contenido)):
        raise CartographyError("El fichero .xlsx no es un ZIP válido")

    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as libro:
            entradas = libro.infolist()
            if len(entradas) > 100:
                raise CartographyError("El XLSX contiene más de 100 entradas")
            nombres = {entrada.filename for entrada in entradas}
            requeridos = {"xl/workbook.xml", "xl/sharedStrings.xml", "xl/worksheets/sheet1.xml"}
            if not requeridos.issubset(nombres):
                raise CartographyError("El XLSX no contiene la estructura esperada del libro INE")
            total_expandido = sum(entrada.file_size for entrada in entradas)
            if total_expandido > 40 * 1024 * 1024:
                raise CartographyError("El XLSX supera el máximo expandido de 40 MiB")
            if any(
                entrada.filename.startswith(("/", "\\")) or ".." in Path(entrada.filename).parts for entrada in entradas
            ):
                raise CartographyError("El XLSX contiene rutas internas no permitidas")
            compartidos_xml = libro.read("xl/sharedStrings.xml")
            hoja_xml = libro.read("xl/worksheets/sheet1.xml")
    except (zipfile.BadZipFile, KeyError, OSError) as error:
        raise CartographyError("No se pudo leer la estructura XLSX del INE") from error

    espacio = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    try:
        compartidos_raiz = ET.fromstring(compartidos_xml)
        hoja_raiz = ET.fromstring(hoja_xml)
        compartidos = ["".join(nodo.itertext()) for nodo in compartidos_raiz.findall("x:si", espacio)]
    except ET.ParseError as error:
        raise CartographyError("El XML interno del XLSX no es válido") from error
    if len(compartidos) > 50_000:
        raise CartographyError("El XLSX contiene demasiadas cadenas compartidas")

    filas_csv: list[list[str]] = []
    for fila in hoja_raiz.findall(".//x:sheetData/x:row", espacio):
        celdas: dict[str, str] = {}
        for celda in fila.findall("x:c", espacio):
            referencia = celda.get("r", "")
            columna = re.sub(r"\d", "", referencia).upper()
            valor = celda.findtext("x:v", default="", namespaces=espacio)
            if celda.get("t") == "s" and valor:
                try:
                    valor = compartidos[int(valor)]
                except (ValueError, IndexError) as error:
                    raise CartographyError(f"Índice de cadena compartida inválido: {referencia}") from error
            elif celda.get("t") == "inlineStr":
                inline = celda.find("x:is", espacio)
                valor = "" if inline is None else "".join(inline.itertext())
            celdas[columna] = valor
        filas_csv.append([celdas.get(columna, "") for columna in "ABCDE"])

    if (
        len(filas_csv) < 3
        or filas_csv[0][0]
        != "Relación de municipios y códigos por comunidades autónomas y provincias a 1 de enero de 2026"
    ):
        raise CartographyError("El XLSX no parece ser el diccionario municipal INE 2026")
    csv_temporal = io.StringIO()
    escritor = csv.writer(csv_temporal)
    escritor.writerows(filas_csv)
    csv_temporal.seek(0)
    return _read_ine_csv_rows(csv_temporal)


def _read_ine_csv_rows(archivo: io.StringIO, dialecto: Any = csv.excel) -> dict[str, dict[str, str]]:
    """Valida filas ya decodificadas del CSV o de la hoja del XLSX."""
    filas = list(csv.reader(archivo, dialecto))
    encabezado_idx = None
    encabezados: list[str] = []
    for indice, fila in enumerate(filas[:10]):
        normalizados = [celda.strip().upper() for celda in fila]
        if {"CODAUTO", "CPRO", "CMUN", "NOMBRE"}.issubset(normalizados):
            encabezado_idx = indice
            encabezados = normalizados
            break
    if encabezado_idx is None:
        raise CartographyError("No se encuentra una cabecera INE con CODAUTO, CPRO, CMUN y NOMBRE")
    posiciones = {nombre: encabezados.index(nombre) for nombre in ("CODAUTO", "CPRO", "CMUN", "NOMBRE")}
    municipios: dict[str, dict[str, str]] = {}
    for numero_fila, fila in enumerate(filas[encabezado_idx + 1 :], start=encabezado_idx + 2):
        if not fila or not any(celda.strip() for celda in fila):
            continue
        if len(fila) <= max(posiciones.values()):
            raise CartographyError(f"Fila INE {numero_fila}: faltan columnas")
        ccaa = fila[posiciones["CODAUTO"]].strip()
        cpro = fila[posiciones["CPRO"]].strip()
        cmun = fila[posiciones["CMUN"]].strip()
        nombre = fila[posiciones["NOMBRE"]].strip()
        if not (ccaa.isdigit() and cpro.isdigit() and cmun.isdigit()):
            continue
        ccaa, cpro, cmun = ccaa.zfill(2), cpro.zfill(2), cmun.zfill(3)
        codigo = cpro + cmun
        if not re.fullmatch(r"\d{5}", codigo) or not nombre:
            raise CartographyError(f"Fila INE {numero_fila}: código o nombre inválido")
        if codigo in municipios:
            raise CartographyError(f"Código municipal INE duplicado: {codigo}")
        municipios[codigo] = {"ccaa_ine": ccaa, "cpro": cpro, "nombre_ine": nombre}
        if len(municipios) > MAX_INE_ROWS:
            raise CartographyError("La relación INE supera el límite de 10.000 municipios")
    if len(municipios) != 8132:
        raise CartographyError(
            f"La relación INE debe contener 8.132 municipios vigentes; contiene {len(municipios)}. "
            "Comprueba el año de referencia y la hoja exportada."
        )
    return municipios


def read_ine_reference(ruta: Path) -> dict[str, dict[str, str]]:
    if ruta.suffix.lower() == ".xlsx":
        return read_ine_xlsx(ruta)
    return read_ine_csv(ruta)


def load_page(
    offset: int,
    cache_dir: Path,
    pausa: float,
    limite: int,
    sin_geometria: bool = False,
) -> dict[str, Any]:
    """Obtiene una página GeoJSON con caché local, pausa y reintentos."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    sufijo_cache = "_sin_geometria" if sin_geometria else ""
    cache_path = cache_dir / f"ign_administrativeunit_{offset:05d}{sufijo_cache}.json"
    if not sin_geometria and not cache_path.is_file():
        cache_atributos = cache_dir / f"ign_administrativeunit_{offset:05d}_sin_geometria.json"
        if cache_atributos.is_file():
            cache_path = cache_atributos
            sin_geometria = True
    if cache_path.is_file() and time.time() - cache_path.stat().st_mtime < 24 * 60 * 60:
        if cache_path.stat().st_size > MAX_RESPONSE_BYTES:
            raise ResponseTooLargeError(f"Página de caché IGN supera el máximo: {cache_path}")
        datos = cache_path.read_bytes()
    else:
        parametros = {"f": "json", "limit": limite, "offset": offset}
        if sin_geometria:
            parametros["skipGeometry"] = "true"
        query = urllib.parse.urlencode(parametros)
        peticion = urllib.request.Request(
            f"{ITEMS_URL}?{query}",
            headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json, application/json"},
        )
        for intento in range(5):
            try:
                with urllib.request.urlopen(peticion, timeout=90) as respuesta:
                    if respuesta.status != 200:
                        raise CartographyError(f"IGN respondió HTTP {respuesta.status}")
                    datos = respuesta.read(MAX_RESPONSE_BYTES + 1)
                    if len(datos) > MAX_RESPONSE_BYTES:
                        raise ResponseTooLargeError("La página IGN supera el máximo de 40 MiB")
                    tipo = respuesta.headers.get_content_type()
                    if tipo not in {"application/geo+json", "application/json"}:
                        raise CartographyError(f"Tipo de contenido IGN inesperado: {tipo}")
                cache_path.write_bytes(datos)
                break
            except (urllib.error.URLError, TimeoutError, CartographyError) as error:
                if isinstance(error, ResponseTooLargeError):
                    raise
                if intento == 4:
                    raise CartographyError(f"Falló la página IGN offset={offset} tras 5 intentos: {error}") from error
                time.sleep(2**intento)
        time.sleep(pausa)

    try:
        resultado = json.loads(datos)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CartographyError(f"Respuesta IGN no es JSON válido en offset={offset}") from error
    if not isinstance(resultado, dict) or resultado.get("type") != "FeatureCollection":
        raise CartographyError(f"IGN no devolvió una FeatureCollection en offset={offset}")
    if not isinstance(resultado.get("features"), list):
        raise CartographyError(f"La página IGN no contiene una lista de elementos en offset={offset}")
    resultado["_geometria_omitida"] = sin_geometria
    return resultado


def validate_geometry(geometria: Any, identificador: str) -> None:
    """Comprueba estructura GeoJSON poligonal y coordenadas CRS84."""
    if not isinstance(geometria, dict) or geometria.get("type") not in {"Polygon", "MultiPolygon"}:
        raise CartographyError(f"Geometría poligonal ausente o inesperada: {identificador}")
    coordenadas = geometria.get("coordinates")
    if not isinstance(coordenadas, list) or not coordenadas:
        raise CartographyError(f"Geometría sin coordenadas: {identificador}")
    pila = [coordenadas]
    vertices = 0
    while pila:
        valor = pila.pop()
        if (
            isinstance(valor, list)
            and len(valor) == 2
            and all(isinstance(numero, (int, float)) and not isinstance(numero, bool) for numero in valor)
        ):
            longitud, latitud = valor
            if not (-180 <= longitud <= 180 and -90 <= latitud <= 90):
                raise CartographyError(f"Coordenada fuera de CRS84: {identificador}")
            vertices += 1
        elif isinstance(valor, list):
            pila.extend(valor)
        else:
            raise CartographyError(f"Coordenada GeoJSON inválida: {identificador}")
    if vertices < 4:
        raise CartographyError(f"Anillo poligonal demasiado corto: {identificador}")


def transform_feature(
    feature: dict[str, Any],
    fecha_referencia: str,
    ine: dict[str, dict[str, str]],
) -> tuple[str, dict[str, Any]]:
    propiedades = feature.get("properties")
    codigo = propiedades.get("nationalcode") if isinstance(propiedades, dict) else None
    nivel = propiedades.get("nationallevelname") if isinstance(propiedades, dict) else None
    nombre = propiedades.get("nameunit") if isinstance(propiedades, dict) else None
    if not isinstance(codigo, str) or not codigo.isdigit() or not isinstance(nivel, str):
        raise CartographyError(f"Elemento IGN sin nationalcode/nationallevelname: {feature.get('id')}")
    validate_geometry(feature.get("geometry"), codigo)

    base = {
        "nationalcode": codigo,
        "nombre": nombre if isinstance(nombre, str) else "",
        "nivel_ign": nivel,
        "fecha_referencia": fecha_referencia,
        "fuente": "IGN/CNIG API Features administrativeunit",
    }

    def salida(capa: str) -> tuple[str, dict[str, Any]]:
        return capa, {
            "type": "Feature",
            "id": int(codigo),
            "geometry": feature["geometry"],
            "properties": base,
        }

    nivel_normalizado = nivel.casefold()
    if nivel_normalizado == "municipio":
        ine_codigo = codigo[-5:]
        registro = ine.get(ine_codigo)
        # El código de unidad IGN contiene 34 + CCAA + CPRO + código municipal INE.
        if registro is not None:
            esperado = "34" + registro["ccaa_ine"] + registro["cpro"] + ine_codigo
            if codigo != esperado:
                raise CartographyError(
                    f"El código IGN {codigo} no coincide exactamente con INE {ine_codigo} ({esperado})"
                )
            base.update(
                {
                    "ine_municipio": ine_codigo,
                    "cpro": registro["cpro"],
                    "ccaa_ine": registro["ccaa_ine"],
                    "nombre": registro["nombre_ine"],
                }
            )
            return salida("municipios")

    if nivel_normalizado == "provincia":
        if len(codigo) < 6:
            raise CartographyError(f"Código IGN de provincia demasiado corto: {codigo}")
        base["cpro"] = codigo[4:6]
        base["ccaa_ine"] = codigo[2:4]
        return salida("provincias")
    if nivel_normalizado in {"comunidad autónoma", "comunidad autonoma"}:
        if len(codigo) < 4:
            raise CartographyError(f"Código IGN de comunidad autónoma demasiado corto: {codigo}")
        base["ccaa_ine"] = codigo[2:4]
        return salida("ccaa")
    base["codigo_ine"] = None
    return salida("unidades_auxiliares")


def audit_auxiliary_overlaps(ruta_municipios: Path, ruta_auxiliares: Path, salida: Path) -> None:
    """Registra intersecciones exactas si Shapely está disponible."""
    try:
        from shapely.geometry import shape
        from shapely.strtree import STRtree
    except ImportError:
        print("AVISO: Shapely no está instalado; no se ejecuta auditoría exacta de solapes.", file=sys.stderr)
        return

    with ruta_municipios.open(encoding="utf-8") as archivo:
        features_municipales = json.load(archivo)["features"]
    with ruta_auxiliares.open(encoding="utf-8") as archivo:
        features_auxiliares = json.load(archivo)["features"]
    geometrias = [shape(feature["geometry"]) for feature in features_municipales]
    arbol = STRtree(geometrias)
    indices_por_id = {id(geometria): indice for indice, geometria in enumerate(geometrias)}
    relaciones = []
    for feature in features_auxiliares:
        geometria = shape(feature["geometry"])
        intersecciones = []
        for candidato in arbol.query(geometria):
            if isinstance(candidato, numbers.Integral):
                indice = int(candidato)
            else:
                # Shapely 1 devuelve geometrías; Shapely 2 devuelve índices.
                indice = indices_por_id[id(candidato)]
            municipio = features_municipales[indice]
            if geometria.intersects(geometrias[indice]):
                intersecciones.append(municipio["properties"]["ine_municipio"])
        relaciones.append(
            {
                "nationalcode": feature["properties"]["nationalcode"],
                "nombre": feature["properties"]["nombre"],
                "municipios_intersectados": sorted(intersecciones),
            }
        )
    salida.write_text(
        json.dumps(
            {
                "fuente": "IGN/CNIG API Features administrativeunit",
                "metodo": "intersects de Shapely sobre geometrías en CRS84",
                "nota": "La intersección no implica que la unidad auxiliar sea un municipio INE.",
                "unidades": relaciones,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def build_label(feature: dict[str, Any], capa: str) -> dict[str, Any]:
    """Un punto interior del polígono mayor, antes de dividirlo en teselas.

    El tramo interior más ancho de la línea horizontal central evita los
    centroides fuera de polígonos cóncavos y respeta los huecos interiores.
    """
    geometria = feature["geometry"]
    poligonos = geometria["coordinates"]
    if geometria["type"] == "Polygon":
        poligonos = [poligonos]

    def area_anillo(anillo: list) -> float:
        return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in pairwise(anillo)))

    poligono = max(poligonos, key=lambda p: area_anillo(p[0]) - sum(area_anillo(a) for a in p[1:]))
    latitudes = [p[1] for p in poligono[0]]
    latitud = (min(latitudes) + max(latitudes)) / 2
    cortes = sorted(
        a[0] + (latitud - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
        for anillo in poligono
        for a, b in pairwise(anillo)
        if (a[1] > latitud) != (b[1] > latitud)
    )
    if len(cortes) < 2 or len(cortes) % 2:
        raise CartographyError(f"No se pudo situar la etiqueta de {feature['id']}")
    izquierda, derecha = max(zip(cortes[::2], cortes[1::2], strict=True), key=lambda par: par[1] - par[0])
    if derecha <= izquierda:
        raise CartographyError(f"Etiqueta sin tramo interior: {feature['id']}")
    propiedades = feature["properties"]
    oeste = sur = float("inf")
    este = norte = float("-inf")
    for componente in poligonos:
        for anillo in componente:
            for longitud, latitud_vertice in anillo:
                oeste, este = min(oeste, longitud), max(este, longitud)
                sur, norte = min(sur, latitud_vertice), max(norte, latitud_vertice)
    return {
        "type": "Feature",
        "id": feature["id"],
        "geometry": {"type": "Point", "coordinates": [(izquierda + derecha) / 2, latitud]},
        "properties": {
            "nombre": propiedades["nombre"],
            "capa": capa,
            "nationalcode": propiedades["nationalcode"],
            "ccaa_ine": propiedades["ccaa_ine"],
            "cpro": propiedades.get("cpro"),
            "ine_municipio": propiedades.get("ine_municipio"),
            "limites": [[oeste, sur], [este, norte]],
            "fecha_referencia": propiedades["fecha_referencia"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ine-csv", type=Path, required=True, help="Official INE 2026 XLSX or exported CSV")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apps/web/public/data/administrativo.pmtiles"),
        help="Output PMTiles path",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "mapa-electricas-ign-cache",
        help="Temporary IGN page cache (under /tmp by default)",
    )
    parser.add_argument("--reference-date", default=date.today().isoformat(), help="Snapshot reference date")
    parser.add_argument("--request-delay", type=float, default=1.0, help="Delay between IGN requests in seconds")
    parser.add_argument(
        "--overlap-audit",
        type=Path,
        help="Write the Shapely intersection audit to this path when available",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Download and validate data without requiring tippecanoe or creating PMTiles",
    )
    parser.add_argument(
        "--labels-only",
        action="store_true",
        help="Validate the download and generate labels without rebuilding PMTiles",
    )
    args = parser.parse_args()

    try:
        datetime.strptime(args.reference_date, "%Y-%m-%d")
        if args.request_delay < 0:
            raise CartographyError("La pausa no puede ser negativa")
        ine = read_ine_reference(args.ine_csv)
        vistos = 0
        total_esperado: int | None = None
        codigos_vistos: set[str] = set()
        claves_ine: set[str] = set()
        municipios_sin_ine: set[str] = set()
        niveles: dict[str, int] = {}
        recuentos = {capa: 0 for capa in LAYERS}
        pais_omitido = 0
        etiquetas = []

        with tempfile.TemporaryDirectory(prefix="mapa-electricas-cartografia-") as temporal:
            temporal_dir = Path(temporal)
            archivos = {capa: (temporal_dir / f"{capa}.geojson").open("w", encoding="utf-8") for capa in LAYERS}
            for archivo in archivos.values():
                archivo.write('{"type":"FeatureCollection","features":[\n')
            separadores = {capa: "" for capa in LAYERS}
            offset = 0
            while True:
                try:
                    pagina = load_page(offset, args.cache_dir, args.request_delay, PAGE_LIMIT)
                except ResponseTooLargeError:
                    print(
                        f"Página IGN de {PAGE_LIMIT} elementos supera 40 MiB en offset={offset}; "
                        "se reintenta con límite 1.",
                        file=sys.stderr,
                    )
                    time.sleep(args.request_delay)
                    try:
                        pagina = load_page(offset, args.cache_dir, args.request_delay, 1)
                    except ResponseTooLargeError:
                        print(
                            f"Feature individual supera 40 MiB en offset={offset}; "
                            "se valida sin geometría para permitir solo País/España.",
                            file=sys.stderr,
                        )
                        time.sleep(args.request_delay)
                        pagina = load_page(offset, args.cache_dir, args.request_delay, 1, sin_geometria=True)
                total = pagina.get("numberMatched")
                if not isinstance(total, int) or total <= 0:
                    raise CartographyError(f"IGN no declara numberMatched válido en offset={offset}")
                if total_esperado is None:
                    total_esperado = total
                elif total != total_esperado:
                    raise CartographyError("Cambió numberMatched durante la descarga; repite la ejecución")
                features = pagina["features"]
                if not features:
                    break
                for feature in features:
                    if not isinstance(feature, dict) or feature.get("type") != "Feature":
                        raise CartographyError(f"Feature GeoJSON inválida en offset={offset}")
                    propiedades = feature.get("properties")
                    codigo_bruto = propiedades.get("nationalcode") if isinstance(propiedades, dict) else None
                    nivel_bruto = propiedades.get("nationallevelname") if isinstance(propiedades, dict) else None
                    if feature.get("geometry") is None:
                        if codigo_bruto != "34000000000" or nivel_bruto != "País":
                            raise CartographyError(
                                f"Geometría ausente fuera del único país permitido: {codigo_bruto} ({nivel_bruto})"
                            )
                        codigo, nivel = codigo_bruto, nivel_bruto
                        pais_omitido += 1
                        if pagina.get("_geometria_omitida") is not True:
                            print("País/España no tiene geometría en IGN; se omite de las capas.", file=sys.stderr)
                    else:
                        capa, preparado = transform_feature(feature, args.reference_date, ine)
                        codigo = preparado["properties"]["nationalcode"]
                        nivel = preparado["properties"]["nivel_ign"]
                    niveles[nivel] = niveles.get(nivel, 0) + 1
                    if codigo in codigos_vistos:
                        raise CartographyError(f"nationalcode IGN duplicado: {codigo}")
                    codigos_vistos.add(codigo)
                    if feature.get("geometry") is None:
                        continue
                    if capa == "municipios":
                        ine_codigo = preparado["properties"]["ine_municipio"]
                        if ine_codigo in claves_ine:
                            raise CartographyError(f"Código municipal INE duplicado en IGN: {ine_codigo}")
                        claves_ine.add(ine_codigo)
                    elif nivel.casefold() == "municipio":
                        municipios_sin_ine.add(codigo)
                    archivos[capa].write(
                        separadores[capa] + json.dumps(preparado, ensure_ascii=False, separators=(",", ":"))
                    )
                    separadores[capa] = ",\n"
                    recuentos[capa] += 1
                    if capa != "unidades_auxiliares" and preparado["properties"]["ccaa_ine"] in {
                        f"{numero:02d}" for numero in range(1, 20)
                    }:
                        etiquetas.append(build_label(preparado, capa))
                devueltos = pagina.get("numberReturned")
                if devueltos != len(features):
                    raise CartographyError(f"numberReturned no coincide con features en offset={offset}")
                vistos += len(features)
                offset += len(features)
                if vistos >= total_esperado:
                    break
            for archivo in archivos.values():
                archivo.write("\n]}\n")
                archivo.close()

            if vistos != total_esperado:
                raise CartographyError(f"IGN declaró {total_esperado} elementos y se descargaron {vistos}")
            if pais_omitido != 1:
                raise CartographyError(f"Se esperaba omitir solo País/España; se omitieron {pais_omitido}")
            faltan = sorted(set(ine) - claves_ine)
            if faltan:
                raise CartographyError(f"Faltan {len(faltan)} códigos INE en IGN; ejemplos: {faltan[:10]}")
            if recuentos["municipios"] != len(ine):
                raise CartographyError(
                    f"IGN aporta {recuentos['municipios']} municipios emparejados, no los {len(ine)} del INE"
                )
            if len(municipios_sin_ine) != 81 or any(
                not re.search(r"53\d{3}$", codigo) for codigo in municipios_sin_ine
            ):
                raise CartographyError(
                    "Se esperaba validar 81 municipios auxiliares IGN con sufijo 53xxx; "
                    f"se encontraron {len(municipios_sin_ine)}"
                )

            print(f"Elementos IGN validados: {vistos} (numberMatched={total_esperado})")
            print("Niveles IGN: " + ", ".join(f"{nivel}={cantidad}" for nivel, cantidad in sorted(niveles.items())))
            print("Capas: " + ", ".join(f"{capa}={cantidad}" for capa, cantidad in recuentos.items()))
            print(f"Códigos INE exactos: {len(claves_ine)}; códigos INE ausentes: 0")
            print(f"Municipios IGN auxiliares sin código INE: {len(municipios_sin_ine)}")
            print(f"Features País sin geometría omitidos de las capas: {pais_omitido}")
            if args.overlap_audit:
                audit_auxiliary_overlaps(
                    temporal_dir / "municipios.geojson",
                    temporal_dir / "unidades_auxiliares.geojson",
                    args.overlap_audit,
                )

            if args.validate_only:
                return 0
            args.output.parent.mkdir(parents=True, exist_ok=True)
            ruta_etiquetas = args.output.with_suffix(".etiquetas.geojson")
            ruta_etiquetas.write_text(
                json.dumps(
                    {"type": "FeatureCollection", "features": etiquetas},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"Etiquetas únicas generadas: {len(etiquetas)} ({ruta_etiquetas})")
            if args.labels_only:
                return 0
            tippecanoe = shutil.which("tippecanoe")
            if tippecanoe is None:
                raise CartographyError(
                    "Validación completa, pero no se encontró tippecanoe para generar el PMTiles. "
                    "Instálalo por el gestor del sistema antes de ejecutar la generación."
                )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            comando = [
                tippecanoe,
                "--output",
                str(args.output),
                "--force",
                "--minimum-zoom=0",
                "--maximum-zoom=14",
                "--no-feature-limit",
                "--no-tile-size-limit",
                "--quiet",
            ]
            for capa in LAYERS:
                comando.extend(["--named-layer", f"{capa}:{temporal_dir / (capa + '.geojson')}"])
            subprocess.run(comando, check=True)
            if args.output.suffix.lower() != ".pmtiles":
                raise CartographyError("La salida debe tener extensión .pmtiles")
            print(f"PMTiles generated: {args.output}")
        return 0
    except (CartographyError, OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
