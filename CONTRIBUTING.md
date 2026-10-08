# Contribuir al mapa de energía

Las contribuciones se proponen mediante un fork y una pull request hacia
`main` de [chof16/mapa-energia-publico](https://github.com/chof16/mapa-energia-publico).
No necesitas permisos de escritura en este repositorio ni acceso a las cuentas
del mantenedor. Para cambios grandes, abre primero una issue que describa el
problema y la propuesta.

## Preparar una contribución

1. Crea un fork desde GitHub en tu cuenta.
2. Clona tu fork y crea una rama para el cambio:

   ```sh
   git clone https://github.com/TU-USUARIO/mapa-energia-publico.git
   cd mapa-energia-publico
   git remote add upstream https://github.com/chof16/mapa-energia-publico.git
   git switch -c fix/descripcion-del-cambio
   ```

3. Sigue el [README](README.md#desarrollo) para instalar con `uv` y `pnpm`
   y ejecutar la aplicación localmente. Los tests usan datos sintéticos;
   para explorar el mapa real, sigue la [guía de datos](docs/data-sources.md).
4. Haz un cambio acotado y ejecuta las comprobaciones correspondientes.
5. Revisa el contenido antes de crear el commit y envíalo a tu fork:

   ```sh
   git diff
   git status --short
   git add RUTAS-DE-LOS-ARCHIVOS-MODIFICADOS
   git diff --cached
   git commit -m "Describe el cambio"
   git push -u origin fix/descripcion-del-cambio
   ```

6. Abre una pull request desde esa rama hacia `chof16/mapa-energia-publico:main`.
   Describe el problema, el resultado y las comprobaciones realizadas. Los
   siguientes commits enviados a la misma rama actualizan la pull request.

Sustituye los nombres de usuario, rama y archivos de los ejemplos. `origin`
debe apuntar a tu fork; `upstream`, al proyecto original. El mantenedor revisa
las propuestas antes de integrarlas. Publicar código abierto no concede
permiso de push directo al repositorio original.

## Comprobaciones

Desde la raíz, con las dependencias instaladas:

```sh
uv run --all-packages pytest
uv run ruff check .
uv run ruff format --check .
pnpm --dir apps/web test
pnpm --dir apps/web build
git diff --check
```

Ejecuta las comprobaciones pertinentes al cambio y explica en la PR cuáles
pasaron y cuáles no pudiste ejecutar. Los cambios solo de documentación no
requieren ejecutar toda la batería. El build de la web comprueba los tipos.
Si cambias la UI, revisa también el resultado en escritorio y móvil: los
tests no renderizan WebGL real. Añade pruebas cuando cambie el comportamiento.

GitHub Actions ejecuta los checks `Python checks` y `Web checks` en las pull
requests hacia `main` y en los pushes a esa rama. El primero ejecuta Ruff y
los tests de Python; el segundo, los tests de la web y su build con comprobación
de tipos. Usan los lockfiles y datos sintéticos, sin credenciales ni datos de
producción. Las contribuciones externas pueden necesitar que el mantenedor
autorice su primera ejecución de Actions.

Antes de integrar una PR, ambos checks deben pasar sobre una rama actualizada
con `main`, las conversaciones deben estar resueltas y el mantenedor debe
aprobar el cambio. Un cambio posterior a una aprobación requiere nueva revisión.

## Código, fuentes y archivos

- Sigue las convenciones de [AGENTS.md](AGENTS.md): Python con Ruff y SQLAlchemy;
  React organizado por funcionalidades, con TypeScript y pnpm.
- Escribe el código y los comentarios técnicos en inglés; la interfaz y la
  documentación funcional están en español.
- No incluyas `.env` reales, credenciales, datos personales, SQLite, exportaciones
  SQL con datos, mapas generados ni configuración de cuentas o despliegues.
  `.gitignore` ayuda, pero revisa siempre el diff antes de enviar.
- Las correcciones de datos deben explicar su fuente original, fecha, alcance
  y condiciones de reutilización. Usa ejemplos sintéticos en los tests y
  conserva las atribuciones. Consulta las [reglas de datos](docs/data-sources.md).
- El código original está bajo [AGPL-3.0-only](LICENSE). Conserva las licencias
  y atribuciones de terceros; la licencia del código no se extiende a los datos.

Si encuentras una credencial o datos personales expuestos, no los copies en
una issue, un comentario ni una pull request pública.
