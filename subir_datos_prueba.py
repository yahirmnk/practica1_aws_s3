"""
Genera datos de prueba (CSV y JSON) y los sube al bucket S3 en las rutas
que usa ingesta_s3.py. Úsalo solo si tu entorno no trae los archivos ya
cargados. Los datos incluyen inconsistencias a propósito (nulos, números
como texto, fechas como texto) para probar el perfilamiento.

Uso:
    python subir_datos_prueba.py
"""

import io
import json
import os
import random
from datetime import datetime, timedelta

import boto3
import pandas as pd
from botocore.exceptions import ClientError

REGION = os.getenv("AWS_REGION", "us-east-1")
BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "aws-academy-datacenter-bucket")

random.seed(42)
s3 = boto3.client("s3", region_name=REGION)


def crear_bucket_si_no_existe():
    try:
        s3.head_bucket(Bucket=BUCKET_NAME)
        print(f"Bucket existente: {BUCKET_NAME}")
    except ClientError:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET_NAME)
        else:
            s3.create_bucket(Bucket=BUCKET_NAME,
                             CreateBucketConfiguration={"LocationConstraint": REGION})
        print(f"Bucket creado: {BUCKET_NAME}")


def generar_transacciones(n=200):
    inicio = datetime(2026, 1, 1)
    filas = []
    for i in range(1, n + 1):
        monto = round(random.uniform(50, 5000), 2)
        filas.append({
            "id_transaccion": i,
            "fecha": (inicio + timedelta(hours=random.randint(0, 6000))).strftime("%Y-%m-%d %H:%M:%S"),
            "id_cliente": random.randint(1000, 1050),
            # Algunos montos llegan como texto inválido o vacíos
            "monto": random.choice([monto] * 18 + ["N/A", ""]),
            "metodo_pago": random.choice(["tarjeta", "efectivo", "transferencia", None]),
            "sucursal": random.choice(["CDMX", "Puebla", "Monterrey", "Guadalajara"]),
        })
    filas.append(filas[10].copy())  # un duplicado intencional
    return pd.DataFrame(filas)


def generar_logs(n=150):
    inicio = datetime(2026, 9, 1)
    logs = []
    for i in range(n):
        logs.append({
            "id_dispositivo": f"sensor-{random.randint(1, 10):02d}",
            "timestamp": (inicio + timedelta(minutes=5 * i)).isoformat(),
            "estado": random.choice(["OK", "OK", "OK", "WARN", "ERROR"]),
            "lecturas": {
                "temperatura": round(random.uniform(18, 45), 1),
                "humedad": random.choice([round(random.uniform(20, 90), 1), None]),
            },
            "ubicacion": {"planta": random.choice(["A", "B"]), "linea": random.randint(1, 3)},
        })
    return logs


def subir(key, contenido):
    s3.put_object(Bucket=BUCKET_NAME, Key=key, Body=contenido)
    print(f"Subido: s3://{BUCKET_NAME}/{key}")


if __name__ == "__main__":
    crear_bucket_si_no_existe()

    buffer = io.StringIO()
    generar_transacciones().to_csv(buffer, index=False)
    subir("raw/transacciones.csv", buffer.getvalue().encode("utf-8"))

    subir("raw/logs_m2m.json", json.dumps(generar_logs(), ensure_ascii=False).encode("utf-8"))
