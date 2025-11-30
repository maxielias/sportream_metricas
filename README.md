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
PGSSLMODE
PGCHANNELBINDING
CONNECTION_URL
TARGET_USER_ID=<uuid-optional>
```

Notas

- En Windows, `pyarrow` puede necesitar ruedas binarias; usar Python 3.11 suele evitar compilaciones desde fuente.
- No subas `.env` ni archivos con credenciales al repositorio.