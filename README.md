**Proyecto**: `sportream_metricas`
Proyecto: sportream_metricas

Resumen rápido

Entorno virtual recomendado: `./.venv` (Python 3.11).
Cómo ejecutar la app Streamlit localmente y notas sobre dependencias (pyarrow/numpy).

Requisitos

- Python 3.11 instalado en el sistema.

Activar el entorno virtual (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
```

Activar el entorno virtual (CMD)

```cmd
.\.venv\Scripts\activate.bat
```

Instalar dependencias (si no están instaladas)

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Ejecutar la app (Streamlit)

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

La app usa, en orden de preferencia: variables de entorno y, para desarrollo, un archivo `.env`.

Ejemplo mínimo de `.env` (archivo en la raíz, NO comitear):

```env
CONNECTION_URL=postgresql://user:password@host:port/dbname
# o, si usas variables sueltas:
PGHOST=...
PGDATABASE=...
PGUSER=...
PGPASSWORD=...
PGPORT=5432
TARGET_USER_ID=<uuid-optional>
```

Notas

- En Windows, `pyarrow` puede necesitar ruedas binarias; usar Python 3.11 suele evitar compilaciones desde fuente.
- No subas `.env` ni archivos con credenciales al repositorio.

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


