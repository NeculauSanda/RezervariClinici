import pika
import json
import time
import os
import secrets
from datetime import datetime
from app import create_app
from utils.email_handler import send_email_smtp
from utils.pdf_generator import generate_confirmation_pdf
from utils.minIO_proc import upload_file_to_minio

# config conectare RabbitMQ
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'rabbitmq')
QUEUE_NAME = 'notifications_queue'

app = create_app()

def procesare_cerere(ch, method, properties, body):
    """
    Procesez mesajele venite de producator 
    """
    with app.app_context():
        data = json.loads(body)
        
        print(f"Procesez mailul pentru {data['patient_email']}")
        email = data.get('patient_email')
        mesaj = data.get('message', '')
        status = data.get('status')
        subiect = f"Notificare Clinica, Programarea {data.get('appointment_id')} - Status: {data.get('status', 'Info')}"

        succes = False

        pdf_bytes = None
        pdf_name = None
        url_minio = None
    
        # GENERARE PDF SI UPLOAD IN MINIO (DOAR DACA PROGRAMAREA E CONFIRMATA)
        if status == 'CONFIRMED':
            try:
                print("Generare PDF")
                pdf_bytes = generate_confirmation_pdf(data)
                # generez un nume unic pt pdf ca sa nu fie usor de ghicit(pt ca la mine bucketul e public)
                token = secrets.token_urlsafe(16)
                pdf_name = f"programare_{data.get('appointment_id')}_{token}.pdf"
                
                print("Upload MinIO")
                url_minio = upload_file_to_minio(pdf_bytes, pdf_name)
                
                if url_minio:
                    print(f"PDF incarcat: {url_minio}")
                    mesaj += f"Puteti descarca confirmarea PDF de aici: {url_minio}"
                else:
                    print("Eroare url nu exista dupa upload")
            except Exception as e:
                print(f"Eroare la generare/upload PDF: {e}")

        if email:
            # se trimite emailul
            succes = send_email_smtp(email, subiect, mesaj, attachment_data=pdf_bytes, attachment_name=pdf_name)
            if succes:
                print(f"Email trimis catre {email}")
            else:
                print(f"Eroare la trimiterea email-ului")

        from bd_struc_flask import db, Notification, NotificationType, NotificationStatus

        # salvez notificarile automate(emailurile) care sunt trimise, si in BD ca sa pot sa 
        # le vad in istoric dupa
        notificare = Notification(
            user_id=data.get('user_id'),
            appointment_id=data.get('appointment_id'),
            type=NotificationType.EMAIL,
            message=mesaj,
            status=NotificationStatus.SENT if succes else NotificationStatus.FAILED,
            sent_at=datetime.utcnow() if succes else None
        )
        db.session.add(notificare)
        db.session.commit()

        # confirmam procesarea email si stergem cererea din coada
        ch.basic_ack(delivery_tag=method.delivery_tag)

def start_worker():
    """
    Se porneste consumatorul ii dau localhost-ul ca sa poata comunica cu producatorul
    Declar o coada persistenta in bd lui RabbitMQ si astept mesajele de la producator
    ca sa fie procesate, cate unu pe rand, pt asta se activeaza bucla infinita care asteapta
    si apeleaza functia de procesare pt fiecare mesaj cand il primeste
    """
    connection = None
    while not connection:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        except pika.exceptions.AMQPConnectionError:
            print("RabbitMQ nu este gata. Asteapta, se mai incarca inca odata")
            time.sleep(5)

    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=procesare_cerere)

    print('Consumator activ, se astapta mail-urile sa fie procesate')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        print("Pornirea consumatorului pentru procesarea email-urilor")
        start_worker()
    except KeyboardInterrupt:
        print("Oprire consumator")