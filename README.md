**Proyecto**: `sportream_metricas`

**Resumen r�pido**
- Entorno virtual recomendado: `./.venv` (Python 3.11).
- C�mo ejecutar la app Streamlit localmente y notas sobre dependencias (pyarrow/numpy).

**Requisitos**
- Python 3.11 instalado en el sistema.

**Activar el entorno virtual (PowerShell)**
```
.\.venv\Scripts\Activate.ps1
```

**Activar el entorno virtual (CMD)**
```
.\.venv\Scripts\activate.bat
```

**Instalar dependencias (si no est�n instaladas)**
```
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**Ejecutar la app (Streamlit)**
```
.\.venv\Scripts\python.exe -m streamlit run app.py
```

**Notas importantes**
- Para evitar compilaciones locales de `pyarrow` en Windows se usa `Python 3.11` y una rueda binaria precompilada; por eso el proyecto proporciona y recomienda `./.venv`.
- Si ves errores relacionados con `numpy` y m�dulos precompilados, aseg�rate de usar la versi�n incluida en el venv (`numpy==1.25.2` con `pyarrow==12.0.0` en el venv `./.venv`).
- Si prefieres usar otro entorno, es posible que `pyarrow` necesite compilaci�n local y herramientas adicionales (CMake/Build Tools).

**Configurar VS Code para usar el int�rprete del venv**
- Archivo de configuraci�n (opcional): crea `.vscode/settings.json` con esta entrada:
```
{
  "python.defaultInterpreterPath": "${workspaceFolder}\\\.venv\\Scripts\\python.exe"
}
```

Si quieres que actualice `.vscode/settings.json` por ti, d�melo y lo hago.

**Comprobaci�n r�pida**
- Despu�s de activar el venv, prueba:
```
.\.venv\Scripts\python.exe -c "import pyarrow,pandas,streamlit,plotly; print('OK', pyarrow.__version__)"
```

**Configurar secrets / variables de entorno (desarrollo local y Streamlit Cloud)**

Esta app carga credenciales en este orden de preferencia: (1) `st.secrets` (cuando se ejecuta en Streamlit Cloud o local con `.streamlit/secrets.toml`), (2) variables de entorno del sistema, y como último recurso (solo para desarrollo) `neondb_keys.json`.

1) Usar variables de entorno (PowerShell, recomendado para pruebas locales)


Abre PowerShell en la raíz del repo y establece las variables de entorno con tus valores (ejemplo con placeholders):

```powershell
# Reemplaza los valores en mayúsculas por tus credenciales/valores reales
$env:PGHOST = '<PGHOST>'
$env:PGDATABASE = '<PGDATABASE>'
$env:PGUSER = '<PGUSER>'
$env:PGPASSWORD = '<PGPASSWORD>'
$env:PGPORT = '<PGPORT>'
$env:PGSSLMODE = '<PGSSLMODE>'
$env:TARGET_USER_ID = '<TARGET_USER_ID>'

# Ejecuta Streamlit en la misma sesión para que vea las vars
streamlit run app.py
```

Estas variables se mantienen solo en la sesión actual de PowerShell y no se guardan en disco.

2) Usar `.streamlit/secrets.toml` (desarrollo local)


Puedes crear localmente `.streamlit/secrets.toml` con este contenido (NO lo subas al repo). Usa placeholders y reemplaza por tus valores:

```toml
PGHOST = "<PGHOST>"
PGDATABASE = "<PGDATABASE>"
PGUSER = "<PGUSER>"
PGPASSWORD = "<PGPASSWORD>"
PGPORT = "<PGPORT>"
PGSSLMODE = "<PGSSLMODE>"
# sportream_metricas

Breve guía para desarrollo local.

Requisitos
- Python 3.11

1) Crear y activar entorno virtual (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Instalar dependencias

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3) Configurar credenciales (local)

La app usa, en orden de preferencia: variables de entorno y, para desarrollo, un archivo `.env`.

Ejemplo mínimo de `.env` (archivo en la raíz, NO comitear):

```
CONNECTION_URL=postgresql://user:password@host:port/dbname
# o, si usas variables sueltas:
PGHOST=...
PGDATABASE=...
PGUSER=...
PGPASSWORD=...
PGPORT=5432
TARGET_USER_ID=<uuid-optional>
```

4) Ejecutar la app

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

5) Comprobación rápida

```powershell
.\.venv\Scripts\python.exe -c "import pyarrow,pandas,streamlit; print('OK')"
```

Notas
- En Windows, `pyarrow` puede requerir ruedas binarias compatibles; usar Python 3.11 suele evitar compilaciones.
- No subas `.env` ni archivos con credenciales al repositorio.

Tests/diagnóstico
- Hay scripts de ayuda en `scripts/` (p. ej. `scripts/test_activity_details.py`) para comprobar conexión y resultados.

Si quieres que deje alguna configuración adicional en el repo (p. ej. `.vscode/settings.json` apuntando al venv), dímelo y lo agrego.


