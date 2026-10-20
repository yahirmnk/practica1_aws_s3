"""
Práctica 1: Perfilamiento e Ingesta Multi-Fuente en AWS S3 con Python.

Descarga objetos CSV y JSON desde un bucket S3 directamente en memoria
(io.BytesIO, sin escribir en disco), los convierte a DataFrames de pandas
y genera un perfilamiento básico: dimensiones, tipos de datos, nulos,
duplicados y estadísticos descriptivos.

Credenciales: NO se escriben en el código. boto3 las toma automáticamente
de ~/.aws/credentials (o de variables de entorno) usando la cadena de
credenciales por defecto. Con AWS Academy deben incluir aws_session_token.

Configuración (opcional) mediante variables de entorno:
    S3_BUCKET_NAME   nombre del bucket   (por defecto: el del código base)
    AWS_REGION       región              (por defecto: us-east-1)
"""

import io
import json
import os
import sys

import boto3
import pandas as pd
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    PartialCredentialsError,
)

# ----------------------------------------------------------------------
# 1. Configuración del cliente boto3
# ----------------------------------------------------------------------
REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "aws-academy-datacenter-bucket")

s3_client = boto3.client("s3", region_name=REGION)

# Columnas cuyo nombre sugiere una fecha; se intentarán convertir a datetime
PALABRAS_FECHA = ("fecha", "date", "timestamp", "time", "hora")


# ----------------------------------------------------------------------
# 2. Lectura desde S3 en memoria
# ----------------------------------------------------------------------
def descargar_objeto(file_key):
    """Descarga un objeto de S3 y devuelve su contenido como bytes (en memoria)."""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_key)
        return response["Body"].read()
    except (NoCredentialsError, PartialCredentialsError):
        sys.exit(
            "ERROR: No se encontraron credenciales de AWS válidas.\n"
            "Copia las credenciales de AWS Academy (AWS Details > AWS CLI) "
            "en ~/.aws/credentials."
        )
    except EndpointConnectionError:
        sys.exit(f"ERROR: No hay conexión con S3 en la región {REGION}.")
    except ClientError as e:
        codigo = e.response["Error"]["Code"]
        mensajes = {
            "NoSuchBucket": f"El bucket '{BUCKET_NAME}' no existe.",
            "NoSuchKey": f"El objeto '{file_key}' no existe en el bucket.",
            "AccessDenied": "Acceso denegado: revisa los permisos del rol/usuario.",
            "ExpiredToken": "La sesión de AWS Academy expiró: actualiza ~/.aws/credentials.",
            "InvalidAccessKeyId": "La Access Key no es válida.",
        }
        print(f"ERROR [{codigo}]: {mensajes.get(codigo, e)}")
        return None


def bytes_a_dataframe(body, is_json=False):
    """Convierte el contenido descargado en un DataFrame."""
    if not is_json:
        # Se prueban codificaciones comunes por si el CSV no viene en UTF-8
        for encoding in ("utf-8", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(body), encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("No se pudo decodificar el CSV.")

    texto = body.decode("utf-8")
    try:
        data_json = json.loads(texto)
    except json.JSONDecodeError:
        # Formato JSON Lines (un objeto JSON por línea), común en logs
        data_json = [json.loads(linea) for linea in texto.splitlines() if linea.strip()]

    # Si el JSON es un objeto con una lista dentro (ej. {"registros": [...]})
    if isinstance(data_json, dict):
        listas = [v for v in data_json.values() if isinstance(v, list)]
        if len(listas) == 1:
            data_json = listas[0]

    # sep="_" aplana campos anidados como sensor.temperatura -> sensor_temperatura
    return pd.json_normalize(data_json, sep="_")


# ----------------------------------------------------------------------
# 3. Limpieza / adecuación de esquema
# ----------------------------------------------------------------------
def ajustar_tipos(df):
    """Corrige inconsistencias comunes de esquema y reporta los cambios."""
    cambios = []

    # Normalizar nombres de columnas
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    for col in df.columns:
        # pandas 2 guarda texto como "object"; pandas 3 como "str"
        es_texto = (pd.api.types.is_object_dtype(df[col])
                    or pd.api.types.is_string_dtype(df[col]))
        if not es_texto:
            continue

        # Textos vacíos o marcadores de nulo -> NaN real
        df[col] = df[col].replace(["", "NA", "N/A", "null", "None", "-"], pd.NA)

        # Columnas de fecha
        if any(p in col for p in PALABRAS_FECHA):
            convertida = pd.to_datetime(df[col], errors="coerce", utc=True)
            if convertida.notna().sum() > 0:
                df[col] = convertida
                cambios.append(f"{col}: object -> datetime")
                continue

        # Columnas numéricas guardadas como texto
        numerica = pd.to_numeric(df[col], errors="coerce")
        no_nulos = df[col].notna().sum()
        if no_nulos and numerica.notna().sum() / no_nulos >= 0.9:
            invalidos = no_nulos - numerica.notna().sum()
            df[col] = numerica
            nota = f" ({invalidos} valores no numéricos -> NaN)" if invalidos else ""
            cambios.append(f"{col}: object -> numérico{nota}")

    return df, cambios


# ----------------------------------------------------------------------
# 4. Perfilamiento
# ----------------------------------------------------------------------
def perfilar(df):
    """Imprime el perfil del DataFrame."""
    print(f"Dimensiones del dataset: {df.shape[0]} filas x {df.shape[1]} columnas")

    print("\nPerfil de tipos de datos, nulos y valores únicos:")
    perfil = pd.DataFrame({
        "tipo": df.dtypes.astype(str),
        "nulos": df.isna().sum(),
        "%_nulos": (df.isna().mean() * 100).round(2),
        "unicos": df.nunique(dropna=True),
    })
    print(perfil)

    # Las columnas con listas/dicts no se pueden comparar para duplicados
    hashables = [c for c in df.columns
                 if not df[c].map(lambda v: isinstance(v, (list, dict))).any()]
    print(f"\nFilas duplicadas: {df[hashables].duplicated().sum()}")

    numericas = df.select_dtypes(include="number")
    if not numericas.empty:
        print("\nEstadísticos descriptivos (cuantitativos):")
        print(numericas.describe().T.round(2))

    categoricas = df.select_dtypes(include=["object", "string", "category"])
    categoricas = categoricas[[c for c in categoricas.columns if c in hashables]]
    if not categoricas.empty:
        print("\nResumen de variables cualitativas:")
        print(categoricas.describe().T)

    fechas = df.select_dtypes(include=["datetime", "datetimetz"])
    for col in fechas.columns:
        print(f"\nRango de fechas en '{col}': {fechas[col].min()} -> {fechas[col].max()}")


def cargar_y_perfilar_s3(file_key, is_json=False):
    """Descarga un archivo de S3 en memoria, ajusta su esquema y lo perfila."""
    print(f"\n{'=' * 70}\n=== Procesando objeto S3: s3://{BUCKET_NAME}/{file_key} ===\n{'=' * 70}")

    body = descargar_objeto(file_key)
    if body is None:
        return None
    if not body:
        print("ADVERTENCIA: el objeto está vacío.")
        return None

    try:
        df = bytes_a_dataframe(body, is_json=is_json)
    except (ValueError, json.JSONDecodeError, pd.errors.ParserError) as e:
        print(f"ERROR al interpretar el archivo: {e}")
        return None

    df, cambios = ajustar_tipos(df)
    if cambios:
        print("Ajustes de esquema aplicados:")
        for c in cambios:
            print(f"  - {c}")
        print()

    perfilar(df)
    return df


# ----------------------------------------------------------------------
# 5. Ejecución
# ----------------------------------------------------------------------
if __name__ == "__main__":
    pd.set_option("display.width", 140)
    pd.set_option("display.max_columns", 20)

    df_transacciones = cargar_y_perfilar_s3("raw/transacciones.csv")
    df_logs = cargar_y_perfilar_s3("raw/logs_m2m.json", is_json=True)
