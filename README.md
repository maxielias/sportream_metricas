**Proyecto**: `sportream_metricas`

**Resumen rápido**
- Entorno virtual recomendado: `./.venv` (Python 3.11).
- Cómo ejecutar la app Streamlit localmente y notas sobre dependencias (pyarrow/numpy).

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

**Instalar dependencias (si no están instaladas)**
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
- Si ves errores relacionados con `numpy` y módulos precompilados, asegúrate de usar la versión incluida en el venv (`numpy==1.25.2` con `pyarrow==12.0.0` en el venv `./.venv`).
- Si prefieres usar otro entorno, es posible que `pyarrow` necesite compilación local y herramientas adicionales (CMake/Build Tools).

**Configurar VS Code para usar el intérprete del venv**
- Archivo de configuración (opcional): crea `.vscode/settings.json` con esta entrada:
```
{
  "python.defaultInterpreterPath": "${workspaceFolder}\\\.venv\\Scripts\\python.exe"
}
```

Si quieres que actualice `.vscode/settings.json` por ti, dímelo y lo hago.

**Comprobación rápida**
- Después de activar el venv, prueba:
```
.\.venv\Scripts\python.exe -c "import pyarrow,pandas,streamlit,plotly; print('OK', pyarrow.__version__)"
```

