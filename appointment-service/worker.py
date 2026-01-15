import pika
import json
import time
from datetime import datetime
from app import create_app
from bd_struc_flask import db, Appointment, AppointmentEvent, EventType, AppointmentStatus, Doctor, Schedule

app = create_app()


def producator_mail_queue(data):
    """
    Am nevoie si aici de producatorul pentru emailuri ca sa trimit 
    emailurile atunci cand pacientul face o programare noua(inregistreaza o programarea -> PENDING)
    """
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=app.config['RABBITMQ_HOST']))
        channel = connection.channel()
        channel.queue_declare(queue='notifications_queue', durable=True)
        
        channel.basic_publish( exchange='', routing_key='notifications_queue',
            body=json.dumps(data), properties=pika.BasicProperties(delivery_mode=2))
        connection.close()

    except Exception as e:
        print(f"Eroare producator mail: {e}")

def procesare_cerere(ch, method, properties, body):
    """
    Aici procesez mesajele venite de producatorul din appointments.py
    Eu deja verific cererile de programare din producator inainte sa le trimit in coada
    cum ar fi daca programul de lucru exista la doctor, daca ora se afla in program si daca
    datele sunt trimise bine, ca sa nu mai verific si aici si sa trimit cereri degeaba
    Aici mai ramane sa verific daca exista suprapuneri cu alte programari deja existente,
    adica conflict si pe urma salvez in bd daca e ok, daca nu le resping
    """
    # accesez bd
    with app.app_context():
        data = json.loads(body)

        print(f"Procesez cerere pentru doctorul {data['doctor_id']} la ora {data['start_time']}")
        try:
            format = '%Y-%m-%d %H:%M:%S'
            start_time = datetime.strptime(data['start_time'], format)
            end_time = datetime.strptime(data['end_time'], format)
            doctor_id = data['doctor_id']

            # verific daca exista alta programare pe slotul acela care e confirmata sau in pending
            suprapunere = Appointment.query.filter(
                Appointment.doctor_id == doctor_id,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.status != AppointmentStatus.REJECTED,
                Appointment.start_time < end_time,
                Appointment.end_time > start_time).first()

            # conflict se suprapun cererile
            if suprapunere:
                print(f"CONFLICT: Interval ocupat.Cererea e REJECTED.")

                # salvez refuzul in BD
                cerere_respinsa = Appointment(
                    patient_id=data['patient_id'],
                    doctor_id=doctor_id,
                    cabinet_id=None, 
                    start_time=start_time,
                    end_time=end_time,
                    status=AppointmentStatus.REJECTED,
                    notes="REJECTED: Intervalul orar selectat e deja ocupat."
                )
                db.session.add(cerere_respinsa)
                db.session.commit()

                #se trimit notificare de refuz catre pacient
                notificare = {
                    'user_id': cerere_respinsa.patient_id,
                    'appointment_id': cerere_respinsa.id,
                    'patient_name': data.get('patient_name', 'Pacient'),
                    'patient_email': data.get('patient_email', 'unknown@test.com'),
                    'status': 'REJECTED',
                    'type': 'EMAIL',
                    'message': 'Cererea dvs. a fost refuzata, slotul este deja ocupat'
                }
                producator_mail_queue(notificare)

                # a procesat mesajul si il sterge din coada, altfel vor fi relivrate aletoriu din nou
                ch.basic_ack(delivery_tag=method.delivery_tag)
                return

            # salvez prima cerere pt slotul cerut de pacient in BD (PENDING)
            # daca nu s-a mentionat cabinetul, il iau din profilul doctorului
            cabinet_id = data.get('cabinet_id')
            if not cabinet_id:
                doctor = Doctor.query.get(doctor_id)
                if doctor:
                    cabinet_id = doctor.cabinet_id
                else:
                    cabinet_id = None

            cerere_noua = Appointment(
                patient_id=data['patient_id'],
                doctor_id=doctor_id,
                cabinet_id=cabinet_id,
                start_time=start_time,
                end_time=end_time,
                status=AppointmentStatus.PENDING,
                notes=data.get('notes'))

            db.session.add(cerere_noua)
            db.session.flush()
            
            # creez eveniment pentru programare creata
            event = AppointmentEvent(appointment_id=cerere_noua.id,
                event_type=EventType.CREATED,
                payload={'info': 'S-a creat o noua programare!'}
            )
            db.session.add(event)
            db.session.commit()
            print(f"Programare creata cu succes (ID - {cerere_noua.id})")

            # trimit cerere de procesare email catre workerul de notificari
            notificare = {
                    'user_id': cerere_noua.patient_id,
                    'appointment_id': cerere_noua.id,
                    'patient_name': data.get('patient_name', 'Pacient'),
                    'patient_email': data.get('patient_email', 'unknown@test.com'),
                    'status': 'PENDING',
                    'type': 'EMAIL',
                    'message': 'Cererea dvs. a fost inregistrata si asteapta sa fie confirmata de catre medic. Odata ce medicul va confirma, veti primi o alta notificare prin email.'
                }
            producator_mail_queue(notificare)

        except Exception as e:
            print(f"Eroare: la procesarea mesajului {e}")
            db.session.rollback()
        
        # confirmam procesarea cererii si stergem mesajul din coada
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
            print("Consumatorul se conecteaza la RabbitMQ")
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=app.config['RABBITMQ_HOST']))
        except pika.exceptions.AMQPConnectionError:
            print("RabbitMQ nu este gata. Asteapta, se mai incarca inca odata")
            time.sleep(5)

    channel = connection.channel()
    channel.queue_declare(queue=app.config['RABBITMQ_QUEUE'], durable=True)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=app.config['RABBITMQ_QUEUE'], on_message_callback=procesare_cerere)
    
    print('Consumator activ, se astapta mesajele')
    channel.start_consuming()

if __name__ == '__main__':
    try:
        print("Pornirea consumatorului pentru procesarea cererilor")
        start_worker()
    except KeyboardInterrupt:
        print("Oprire consumator")