from minio import Minio
from minio.commonconfig import GOVERNANCE
from flask import current_app
import io
import json

def minio_client():
    return Minio(
        current_app.config['MINIO_ENDPOINT'],
        access_key=current_app.config['MINIO_ACCESS_KEY'],
        secret_key=current_app.config['MINIO_SECRET_KEY'],
        secure=False
    )

def upload_file_to_minio(file_data, filename, content_type='application/pdf'):
    client = minio_client()
    bucket = current_app.config['MINIO_BUCKET']

    # verific daca bucket-ul exista si il cream daca nu exista
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

    # setam politica de acces public pentru bucket
    politica = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/*"]
            }
        ]
    }
    client.set_bucket_policy(bucket, json.dumps(politica))

    # convertim bytes in stream
    data_stream = io.BytesIO(file_data)
    
    # incarcam fisierul in MinIO
    client.put_object(bucket, filename, data_stream, len(file_data), content_type=content_type)

    # link public catre fisierul pdf
    url = f"http://localhost:9000/{bucket}/{filename}"
    return url