# Práctica 1: Perfilamiento e Ingesta Multi-Fuente en AWS S3 con Python

Script en Python que descarga archivos CSV y JSON desde un bucket de AWS S3
**directamente en memoria** (`io.BytesIO`, sin guardarlos en disco), los
convierte a DataFrames de pandas y genera un perfilamiento de datos.

## Estructura

| Archivo | Descripción |
|---|---|
| `ingesta_s3.py` | Script principal: descarga, ajuste de esquema y perfilamiento |
| `subir_datos_prueba.py` | Genera datos de prueba y los sube al bucket (opcional) |
| `requirements.txt` | Dependencias del proyecto |
| `.gitignore` | Excluye credenciales, llaves y el entorno virtual |

## Requisitos

- Python 3.10 o superior
- Laboratorio de AWS Academy iniciado (Learner Lab)
- Visual Studio Code

## 1. Preparar el entorno

```bash
python -m venv venv
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

## 2. Configurar credenciales de AWS Academy (fuera del repositorio)

En AWS Academy: **AWS Details → AWS CLI → Show**. Copia el bloque completo en
el archivo de credenciales de tu usuario:

- Windows: `C:\Users\<usuario>\.aws\credentials`
- macOS / Linux: `~/.aws/credentials`

```ini
[default]
aws_access_key_id=...
aws_secret_access_key=...
aws_session_token=...
```

> Las credenciales de AWS Academy son temporales: al reiniciar el laboratorio
> hay que copiarlas de nuevo. **Nunca** se escriben en el código ni se suben a Git.

## 3. Configurar el bucket

Los nombres de bucket son únicos en todo AWS. Define el tuyo con una variable
de entorno (o cambia el valor por defecto en el código):

```bash
# Windows (PowerShell):
$env:S3_BUCKET_NAME="mi-bucket-practica1-12345"
# macOS / Linux:
export S3_BUCKET_NAME="mi-bucket-practica1-12345"
```

Si el bucket no tiene los archivos `raw/transacciones.csv` y
`raw/logs_m2m.json`, créalos con:

```bash
python subir_datos_prueba.py
```

## 4. Ejecutar

```bash
python ingesta_s3.py
```

## Ajustes respecto al código base

1. **Credenciales y configuración externas**: bucket y región se leen de variables
   de entorno; las credenciales, de la cadena por defecto de boto3.
2. **Manejo de excepciones**: credenciales ausentes, token expirado, bucket u
   objeto inexistente, acceso denegado y errores de conexión muestran un mensaje claro.
3. **Lectura robusta**: CSV en UTF-8 o Latin-1; JSON normal, JSON Lines o un
   objeto que contiene la lista de registros. Los campos anidados se aplanan con `_`.
4. **Ajuste de esquema**: normaliza nombres de columnas, convierte marcadores de
   nulo (`""`, `N/A`, `null`…) a valores nulos reales, fechas en texto a `datetime`
   y números guardados como texto a tipo numérico.
5. **Perfilamiento ampliado**: tipos, nulos (cantidad y %), valores únicos,
   duplicados, estadísticos numéricos y categóricos, y rango de fechas.
