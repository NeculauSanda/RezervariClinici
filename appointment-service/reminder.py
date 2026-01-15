import time
import pika
import json
import os
from datetime import datetime, timedelta,timezone
from app import create_app
from bd_struc_flask import db, Appointment, AppointmentEvent, EventType, AppointmentStatus, User

app = create_app()

def producator_reminder_mail_queue(data):
    """
    Trimit mesajul in coada pentru notificari
    """
    connection = None
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=os.getenv('RABBITMQ_HOST', 'rabbitmq')))
        channel = connection.channel()
        channel.queue_declare(queue="notifications_queue", durable=True)
        channel.basic_publish(exchange='', routing_key="notifications_queue",
            body=json.dumps(data),properties=pika.BasicProperties(delivery_mode=2)
        )

    except Exception as e:
        print(f"Eroare reminder producator {e}")
    finally:
        if connection:
            connection.close()

def verificare_reminder():
    """
    Verifica programarile care incep intr-o 1 ora si 30 de min (interval)
    """
    with app.app_context():
        
        romania_timp = timezone(timedelta(hours=2))
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        now_romania = now.astimezone(romania_timp).replace(tzinfo=None)

        start_reminder = now_romania + timedelta(minutes=30)
        end_reminder = now_romania + timedelta(minutes=60)

        # selectez programarile confirmate si care se incadreaza in ora de reminder
        programari = db.session.query(Appointment, User).join(User, Appointment.patient_id == User.id).filter(
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.start_time >= start_reminder,
            Appointment.start_time <= end_reminder).all()


        for prog, user in programari:
            # verific daca a mai fost trimisa o notificare de tip reminder pentru aceasta programare
            trimisa = AppointmentEvent.query.filter_by(appointment_id=prog.id, event_type=EventType.REMINDER_DUE).first()

            print(f"notificare trimisa pentru id{prog.id}: {trimisa is not None}")

            if not trimisa:

                # fac eveniment ca s-a stiu ca am trimis deja reminderul pentru aceasta programare
                eveniment = AppointmentEvent(appointment_id=prog.id, event_type=EventType.REMINDER_DUE,
                    payload={'info': 'Notificare de  reminder trimisa'}, is_processed=True)
                
                db.session.add(eveniment)
                db.session.commit()

                mesaj = {
                    'user_id': prog.patient_id,
                    'appointment_id': prog.id,
                    'patient_name': user.full_name,
                    'patient_email': user.email,
                    'doctor_id': prog.doctor_id,
                    'start_time': prog.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'end_time': prog.end_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'REMINDER',
                    'type': 'EMAIL',
                    'message': f"Reminder aveti o programare azi la ora {prog.start_time.strftime('%Y-%m-%d %H:%M')}"
               }
                producator_reminder_mail_queue(mesaj)

            else:
                print(f"Email deja trimis pentru id{prog.id}")
                pass

if __name__ == '__main__':
    """
    Rulez un worker-ul pentru verifica la fiecare 60 de secunde daca sunt programari
    """
    time.sleep(10)

    while True:
        try:
            verificare_reminder()
        except Exception as e:
            print(f"Eroare verificare reminder {e}")

        time.sleep(60)