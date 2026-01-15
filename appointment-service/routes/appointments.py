import pika
import json
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from bd_struc_flask import db, Appointment, AppointmentEvent, EventType, AppointmentStatus, User, Doctor, Schedule, Cabinet
from utils.auth import require_auth, require_role, get_token_from_header, get_user_info_from_token

appointments_bp = Blueprint('appointments', __name__, url_prefix='/appointments')

# ------------- functii ajutatoare ---------------

def producator_mail_queue(data):
    """
    Producatorul pentru emailuri
    """
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=current_app.config['RABBITMQ_HOST'])
        )
        channel = connection.channel()
        channel.queue_declare(queue='notifications_queue', durable=True)
        channel.basic_publish(exchange='', routing_key='notifications_queue',
            body=json.dumps(data), properties=pika.BasicProperties(delivery_mode=2))
        connection.close()
        return True

    except Exception as e:
        print(f"Eroare producator mail: {e}")
        return False

def producator_app_queue(message_dict):
    """
    Producatorul de programari pentru coada
    """
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=current_app.config['RABBITMQ_HOST'])
        )
        channel = connection.channel()
        channel.queue_declare(queue=current_app.config['RABBITMQ_QUEUE'], durable=True)
        
        # schimbul se face fara nume si mesajele sunt redirectionate pe coada appointments_queue
        # mesajele o sa fie persistente ca sa nu le pierd, si la fel si coada
        channel.basic_publish( exchange='', routing_key=current_app.config['RABBITMQ_QUEUE'],
            body=json.dumps(message_dict), properties=pika.BasicProperties(delivery_mode=2)) 
        connection.close()
        return True

    except Exception as e:
        print(f"Eroare producator {e}")
        return False

def programari_finalizate():
    """
    Functie care schimba starea programarilor care s-au finalizat in COMPLETED
    """
    now = datetime.utcnow()
    Appointment.query.filter(
        Appointment.status == AppointmentStatus.CONFIRMED,
        Appointment.end_time < now
    ).update({Appointment.status: AppointmentStatus.COMPLETED})
    db.session.commit()

def info_output_programare(appointment: Appointment):
    """
    Afiseaza info programare datele cele mai importante
    """
    if not appointment:
        return {}

    doctor = Doctor.query.filter_by(id=appointment.doctor_id).first()
    doctor_info = {
        'id': doctor.id,
        'bio': doctor.bio,
        'years_experience': doctor.years_experience,
        'specialization': doctor.specialization.to_dict() if doctor.specialization else None,
        'email': doctor.user.email if doctor.user else None,
        'full_name': doctor.user.full_name if doctor.user else None,
    }

    patient = User.query.filter_by(id=appointment.patient_id).first()
    patient_info = {
        'id': patient.id,
        'full_name': patient.full_name,
        'email': patient.email,
        'phone': patient.phone
    }

    cabinet = None
    if appointment.cabinet_id:
        cabinet = Cabinet.query.get(appointment.cabinet_id)
    
    if cabinet:
        cabinet_info = {
            'name': cabinet.name,
            'location': cabinet.location,
            'floor': cabinet.floor
        }
    else:
        cabinet_info = None
    return {
        'id': appointment.id,
        'patient_info': patient_info,
        'doctor_info': doctor_info,
        'cabinet': cabinet_info,
        'start_time': appointment.start_time.isoformat().replace('T', ' '),
        'end_time': appointment.end_time.isoformat().replace('T', ' '),
        'status': appointment.status,
        'notes': appointment.notes,
        'created_at': appointment.created_at.isoformat().replace('T', ' '),
        'updated_at': appointment.updated_at.isoformat().replace('T', ' ') if appointment.updated_at else None
    }
# -------------------------------------------


@appointments_bp.route('', methods=['GET'])
@require_role('ADMIN', 'DOCTOR')
def get_appointments():
    """
    Afisare programari de catre ADMIN sau DOCTOR, se pot pune si filte
    in functie de doctor, pacient, ziua/zilele(o perioada de tipm pe care se afiseaza)
    staus
    """

    # marcez inainte programarile care s-au terminat ca sunt COMPLETED
    programari_finalizate()

    status = request.args.get('status')
    doctor_id = request.args.get('doctor_id')
    patient_id = request.args.get('patient_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    # aplicam filtrele
    lista_programari = Appointment.query

    if status:
        lista_programari = lista_programari.filter_by(status=status)
    if doctor_id:
        lista_programari = lista_programari.filter_by(doctor_id=doctor_id)
    if patient_id:
        lista_programari = lista_programari.filter_by(patient_id=patient_id)
    
    if date_from:
        try:
            data_from = datetime.strptime(date_from, '%Y-%m-%d')
            lista_programari = lista_programari.filter(Appointment.start_time >= data_from)
        except ValueError:
            pass
            
    if date_to:
        try:
            # Setam la sfarsitul zilei respective
            data_to = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            lista_programari = lista_programari.filter(Appointment.start_time <= data_to)
        except ValueError:
            pass

    # ordonam descrescator ultima facuta e prima
    programari = lista_programari.order_by(Appointment.start_time.desc()).all()

    rez = []
    for a in programari:
        rez.append(info_output_programare(a))

    return jsonify(rez), 200

@appointments_bp.route('/my', methods=['GET'])
@require_auth
def get_my_active_appointments():
    """
    Returneaza programarile active ale pacientului curent care se alfa in starea PENDING sau CONFIRMED
    """

    # marcez inainte programarile care s-au terminat ca sunt COMPLETED
    programari_finalizate()

    external_id = request.user.get('external_id')
    user = User.query.filter_by(external_id=external_id).first()

    if not user:
        return jsonify({'Eroare': 'User inexistent'}), 404

    status_activ = [AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]

    programari = Appointment.query.filter(Appointment.patient_id == user.id,
        Appointment.status.in_(status_activ)).order_by(Appointment.start_time.asc()).all()

    rez = []
    for a in programari:
        rez.append(info_output_programare(a))

    return jsonify(rez), 200

@appointments_bp.route('/my/history', methods=['GET'])
@require_auth
def get_my_history():
    """
    Afisare programari trecute ale utilizatorului curent care sunt instarea COMPLETED/CANCELLED/REJECTED
    filtru dupa status se poate pune
    """

    # marcez inainte programarile care s-au terminat ca sunt COMPLETED
    programari_finalizate()

    external_id = request.user.get('external_id')
    user = User.query.filter_by(external_id=external_id).first()
    if not user: return jsonify({'Eroare': 'User inexistent'}), 404

    status_param = request.args.get('status')

    lista_programari = Appointment.query.filter(Appointment.patient_id == user.id)
    
    if status_param:
        lista_programari = lista_programari.filter(Appointment.status == status_param)
    else:
        status_history = [AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED, AppointmentStatus.REJECTED]
        lista_programari = lista_programari.filter(Appointment.status.in_(status_history))

    programari = lista_programari.order_by(Appointment.start_time.desc()).all()
    rez = []
    for a in programari:
        rez.append(info_output_programare(a))

    return jsonify(rez), 200

@appointments_bp.route('/<int:id>', methods=['GET'])
@require_auth
def get_appointment_details(id):
    """
    Afisare detalii programare dupa id si in functie de user
    pacientul - doar daca e a lui
    doctorul - doar daca e a lui
    admin - oricare
    """
    external_id = request.user.get('external_id')
    user = User.query.filter_by(external_id=external_id).first()
    if not user: return jsonify({'Eroare': 'User inexistent'}), 404

        
    programare = Appointment.query.get(id)
    if not programare:
        return jsonify({'Eroare': 'Programare inexistenta'}), 404
    
    if user.role == 'ADMIN':
        return jsonify(info_output_programare(programare)), 200
    
    elif user.role == 'PATIENT':
        if programare.patient_id != user.id:
            return jsonify({'Eroare': 'Permisiuni insuficiente'}), 403

    elif user.role == 'DOCTOR':
        doctor = Doctor.query.filter_by(user_id=user.id).first()
        if not doctor or doctor.id != programare.doctor_id:
            # daca doctorul nu e nici pacient 
            # (daca e pacient si are rol de doctor il lasam sa si vada programarea de pacient)
            if programare.patient_id != user.id:
                return jsonify({'Eroare': 'Permisiuni insuficiente'}), 403
        return jsonify(info_output_programare(programare)), 200


    return jsonify(info_output_programare(programare)), 200

@appointments_bp.route('', methods=['POST'])
@require_auth
def create_appointment_request():
    """
    Cerere programare de catre pacient
    Mai intai verific daca datele sunt bune ca sa nu trimit degeaba mesajul in coada
    Verificare consta in a verifica daca ziua si ora se afla in programul de lucru al doctorului
    """
    data = request.get_json()
    date_ob = ['doctor_id', 'start_time', 'end_time']
    for i in date_ob:
        if i not in data:
            return jsonify({'Eroare': 'Date insuficiente, trebuie: doctor_id, start_time, end_time'}), 400

    external_id = request.user.get('external_id')
    user = User.query.filter_by(external_id=external_id).first()
    if not user:
        return jsonify({'Eroare': 'User inexistent'}), 404

    try:
        format = '%Y-%m-%d %H:%M:%S'
        start_data = datetime.strptime(data['start_time'], format)
        end_data = datetime.strptime(data['end_time'], format)
    except ValueError:
        return jsonify({'Eroare': 'Format data invalid, foloseste YYYY-MM-DD HH:MM:SS'}), 400

    if start_data >= end_data:
        return jsonify({'Eroare': 'Ora de start trebuie sa fie inaintea orei de incheiere'}), 400

    doctor_id = data['doctor_id']
    weekday = start_data.weekday()

    program_doctor = Schedule.query.filter_by(doctor_id=doctor_id, weekday=weekday).all()
    
    if not program_doctor:
        return jsonify({
            'Eroare': 'REJECT: Doctorul nu lucreaza in aceasta zi',
            'detalii': f'Ziua solicitata: {weekday} (0->Luni, 1->Marti,...6->Duminica)'}), 400
    
    slot_valid = False
    for prog in program_doctor:
        if start_data.time() >= prog.start_time and end_data.time() <= prog.end_time:
            slot_valid = True
            break
    
    timp_lucru_lista = []
    for prog in program_doctor:
        timp_lucru_lista.append(f"{prog.start_time} - {prog.end_time}")

    timp_lucru = " / ".join(timp_lucru_lista)

    # verific daca ora se incadreaza in programul de lucru
    if not slot_valid:
        return jsonify({
            'Eroare': 'REJECT: Ora solicitata este in afara programului de lucru.',
            'program_doctor': f"{timp_lucru}"}), 400

    # daca nu a fost mentionat cabinetul il luam de la doctor
    doctor = None
    cabinet_id = None
    if not data.get('cabinet_id'):
        doctor = Doctor.query.filter_by(id=doctor_id).first()
        if doctor:
            cabinet_id = doctor.cabinet_id

    # info mesaj pentru coada
    message = {
        'patient_id': user.id,
        'patient_name': user.full_name,
        'patient_email': user.email,
        'doctor_id': doctor_id,
        'start_time': data['start_time'],
        'end_time': data['end_time'],
        'notes': data.get('notes', ''),
        'cabinet_id': cabinet_id
    }

    if producator_app_queue(message):
        return jsonify({'message': 'Cererea a fost validata si trimisa spre procesare', 'status': 'QUEUED'}), 202
    else:
        return jsonify({'Eroare': 'Coada de mesaje indisponibila'}), 500

@appointments_bp.route('/<int:id>/cancel', methods=['PUT'])
@require_auth
def cancel_appointment(id):
    """
    Anulare programare de catre pacientul sau doctorul insusi
    doar daca e in PENDING sau CONFIRMED
    """
    programare = Appointment.query.get(id)
    if not programare: return jsonify({'Eroare': 'Programare inexistenta'}), 404

    if programare.status != AppointmentStatus.CONFIRMED and programare.status != AppointmentStatus.PENDING:
        return jsonify({'Eroare': 'Doar programarile in starea de PENDING sau CONFIRMED pot fi anulate'}), 400

    external_id = request.user.get('external_id')
    user = User.query.filter_by(external_id=external_id).first()
    if not user: return jsonify({'Eroare': 'User inexistent'}), 404

    pacient = False
    if programare.patient_id == user.id:
        pacient = True

    doctor = Doctor.query.filter_by(id=programare.doctor_id).first()
    is_doctor = False
    if doctor:
        if doctor.user_id == user.id:
            is_doctor = True
    
    if not (pacient or is_doctor):
        return jsonify({'Eroare': 'Permisiuni insuficiente pentru anulare. Doar pacientul sau doctorul pot anula.'}), 403

    # acualizare status
    programare.status = AppointmentStatus.CANCELLED
    programare.updated_at = datetime.utcnow()

    # actualizam evenimentul pentru programare ca CANCELLED
    event = AppointmentEvent(
        appointment_id=programare.id,
        event_type=EventType.CANCELLED,
        payload={'motiv': f"Programare anulata de {'pacient' if pacient else 'doctor'}"}
    )
    db.session.add(event)
    
    try:
        db.session.commit()

        # verific daca pacientul e in BD si trimit notificarea de anulare(email) sa fie procesata
        user = User.query.get(programare.patient_id)
        if user:
            notificare_data = {
                'user_id': programare.patient_id,
                'appointment_id': programare.id,
                'patient_name': user.full_name,
                'patient_email': user.email,
                'doctor_id': programare.doctor_id,
                'start_time': programare.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': programare.end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'CANCELLED',
                'type': 'EMAIL',
                'message': f"Programarea dumneavoastra a fost anulata de {'dumneavoastra' if pacient else 'catre doctor'}."
            }
            producator_mail_queue(notificare_data)

        return jsonify(info_output_programare(programare)), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': str(e)}), 500

@appointments_bp.route('/<int:id>/confirm', methods=['PUT'])
@require_role('ADMIN', 'DOCTOR')
def confirm_appointment(id):
    """
    Confirmare programare de catre DOCTORUL insusi sau ADMIN, doar daca e in PENDING
    """

    programare = Appointment.query.get(id)
    if not programare: return jsonify({'Eroare': 'Programare inexistenta'}), 404

    if programare.status != AppointmentStatus.PENDING:
        return jsonify({'Eroare': 'Doar programarile PENDING pot fi confirmate'}), 400

    # verific daca doctorul care confirma cererea e cel care are programarea
    external_id = request.user.get('external_id')
    user = User.query.filter_by(external_id=external_id).first()
    if user.role == 'DOCTOR':
        doctor = Doctor.query.filter_by(user_id=user.id).first()
        if not doctor or doctor.id != programare.doctor_id:
            return jsonify({'Eroare': 'Permisiuni insuficiente. Doar doctorul INSUSI poate confirma.'}), 403

    programare.status = AppointmentStatus.CONFIRMED
    programare.updated_at = datetime.utcnow()
    
    # actualizam evenimentul pt notificari
    event = AppointmentEvent(
        appointment_id=programare.id,
        event_type=EventType.UPDATED,
        payload={'info': 'Programare confirmata de medic'})
    db.session.add(event)

    try:
        db.session.commit()

        # trimit notificarea de confirmare(email) sa fie procesata
        user = User.query.get(programare.patient_id)
        if user:
            notificare_data = {
                'user_id': programare.patient_id,
                'appointment_id': programare.id,
                'patient_name': user.full_name,
                'patient_email': user.email,
                'doctor_id': programare.doctor_id,
                'cabinet_id': programare.cabinet_id,
                'start_time': programare.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': programare.end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'CONFIRMED',
                'type': 'EMAIL',
                'message': f"Programarea dumneavoastra a fost CONFIRMATA de catre medic."
            }
            producator_mail_queue(notificare_data)

        return jsonify(info_output_programare(programare)), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': str(e)}), 500

@appointments_bp.route('/<int:id>', methods=['PUT'])
@require_role('ADMIN', 'DOCTOR')
def update_appointment(id):
    """
    Actualizare info programare de catre ADMIN sau DOCTOR doar daca e in PENDING
    Se poate schimba ora, cabinetul, data si pe urma actualizez la evenimente ca a fost actualizata
    programarea (UPDATED)
    """

    programare = Appointment.query.get(id)
    if not programare: return jsonify({'Eroare': 'Programare inexistenta'}), 404

    if programare.status != AppointmentStatus.PENDING:
        return jsonify({'Eroare': 'Doar programarile PENDING pot fi modificate'}), 400

    old_start = programare.start_time
    old_end = programare.end_time

    data = request.get_json()
    format = '%Y-%m-%d %H:%M:%S'
    str_rez = ''
    info_schimbate = []
    # schimbare date
    if 'start_time' in data:
        programare.start_time = datetime.strptime(data['start_time'], format)
        str_rez += "start_time"
        info_schimbate.append('start_time')
        info_schimbate.append(str(programare.start_time.isoformat().replace('T', ' ')))

    if 'end_time' in data:
        programare.end_time = datetime.strptime(data['end_time'], format)
        str_rez += " end_time"
        info_schimbate.append('end_time')
        info_schimbate.append(str(programare.end_time.isoformat().replace('T', ' ')))

    if 'cabinet_id' in data:
        programare.cabinet_id = data['cabinet_id']
        str_rez += " cabinet_id"
        info_schimbate.append('cabinet_id')
        info_schimbate.append(str(programare.cabinet_id))

        
    # verific daca exista conflict cu NOUL SLOT
    if 'start_time' in data or 'end_time' in data:
        conflict = Appointment.query.filter(
            Appointment.doctor_id == programare.doctor_id,
            Appointment.id != int(id), # exclud programarea curenta
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
            Appointment.start_time < programare.end_time,
            Appointment.end_time > programare.start_time
        ).first()

        if conflict:
            return jsonify({'Eroare': 'Noul slot e ocupat! Alege alta ora.'}), 400

    # actualizez data la care s-a facut actualizarea programarii
    programare.updated_at = datetime.utcnow()
    programare.notes = f"Programare actualizata de medic: s-a schimbat {str_rez.strip()}"

    # eveniment de UPDATED pentru a vedea adminul toate schimbarile produse (pt audit)
    event = AppointmentEvent(appointment_id=programare.id,
        event_type=EventType.UPDATED,
        payload={
            'old_start': old_start.isoformat().replace('T', ' '),
            'old_end': old_end.isoformat().replace('T', ' '),
            'new_start': programare.start_time.isoformat().replace('T', ' '),
            'new_end': programare.end_time.isoformat().replace('T', ' '),
            'new_cabinet_id': programare.cabinet_id,
            'info': 'Programare modificata de medic'
        })
    db.session.add(event)

    try:
        db.session.commit()

        # trimit notificarea de update(email) ca sa fie procesata
        user = User.query.get(programare.patient_id)
        if user:

            schimbari_str = ", ".join(info_schimbate) if info_schimbate else "detalii"

            notificare_data = {
                'user_id': programare.patient_id,
                'appointment_id': programare.id,
                'patient_name': user.full_name,
                'patient_email': user.email,
                'doctor_id': programare.doctor_id,
                'start_time': programare.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': programare.end_time.strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'UPDATED',
                'type': 'EMAIL',
                'message': f'Programarea a fost modificata. Actualizari: {schimbari_str}.'
            }
            producator_mail_queue(notificare_data)

        return jsonify(info_output_programare(programare)), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': str(e)}), 500