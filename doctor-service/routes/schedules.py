from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from bd_struc_flask import db, Doctor, Schedule, Appointment, AppointmentStatus, User, UserRole
from utils.auth import require_auth, require_role, get_user_info_from_token, get_token_from_header

# ruta pentru programul doctorilor
schedules_bp = Blueprint('schedules', __name__, url_prefix='/doctors')

@schedules_bp.route('/<int:doctor_id>/schedule', methods=['GET'])
def get_schedule(doctor_id):
    """
    Returneza programul de lucru al doctorului cerut in ordinea zilelor saptamanii
    """
    schedules = Schedule.query.filter_by(doctor_id=doctor_id).order_by(Schedule.weekday).all()
    return jsonify([s.to_dict() for s in schedules]), 200

@schedules_bp.route('/<int:doctor_id>/schedule', methods=['POST'])
@require_auth
def add_schedule_slot(doctor_id):
    """
    Adaugare program de lucru DOAR DE CATRE ADMIN SAU DOCTORUL INSUSI
    Alt doctor nu are cum sa adauge program pentru un alt doctor
    Verific in functie ce rol are
    """

    data = request.get_json()

    # ------- verific daca are permisiunile necesare sa faca operatiunea---------
    token = get_token_from_header()
    user_info = get_user_info_from_token(token)
    external_id = user_info.get('external_id')

    # i-au userul din BD
    user = User.query.filter_by(external_id=external_id).first()
    if not user:
        return jsonify({'Eroare': 'Utilizator necunoscut'}), 404

    # verific daca e ADMIN sau DOCTOR-ul insusi
    is_admin = False
    if user.role == UserRole.ADMIN:
        is_admin = True

    is_doctor = False
    if user.role == UserRole.DOCTOR:
        doctor = Doctor.query.filter_by(user_id=user.id).first()
        if doctor and doctor.id == doctor_id:
            is_doctor = True

    # daca nu e nici una eroare
    if not (is_admin or is_doctor):
        return jsonify({'Eroare': 'Permisiuni insuficiente. Doar ADMIN sau doctorul poate adauga intervale in programul PROPRIU'}), 403

    # -------- date de intrare - validari --------
    obligatorii = ['weekday', 'start_time', 'end_time']
    for i in obligatorii:
        if i not in data:
            return jsonify({'error': 'Date incomplete'}), 400

    # zilele saptamanii intre 0 si 6
    if not isinstance(data['weekday'], int) or data['weekday'] < 0 or data['weekday'] > 6:
        return jsonify({'Eroare': 'Weekday trebuie sa fie intre 0 (Luni) si 6 (Duminica)'}), 400

    # validare ora de start program si ora de final program start < end
    if data['start_time'] >= data['end_time']:
        return jsonify({'Eroare': 'Ora de start trebuie sa fie inaintea orei de final'}), 400

    # validare durata intevale pe sloturi trebuie sa fie mai mare ca 0
    slot_duration = data.get('slot_duration_minutes', 30)
    if slot_duration <= 0:
        return jsonify({'Eroare': 'Durata slotului trebuie sa fie mai mare decat 0 minute'}), 400

    # verific daca doctorul exista
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'Eroare': 'Doctorul nu exista'}), 404

    # Pt a nu pune de doua ori in BD programul de lucru si a avea erori, verifc pt a NU PERMITE DUPLICATELE
    existing_schedule = Schedule.query.filter_by( doctor_id=doctor_id,
        weekday=data['weekday'],
        start_time=data['start_time'],
        end_time=data['end_time']).first()

    if existing_schedule:
        return jsonify({
            'EROARE': 'Programul de lucru exista deja pentru acest doctor pentru ziua si intervalul orar specificat',
            'program': existing_schedule.to_dict()}), 409

    # -------- cream programul de lucru --------
    try:
        new_sch = Schedule(
            doctor_id=doctor_id,
            weekday=data['weekday'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            slot_duration_minutes=data.get('slot_duration_minutes', 30)
        )

        db.session.add(new_sch)
        db.session.commit()
        current_app.logger.info(f"Program adaugat pentru doctor {doctor_id} de catre user-ul {user.id}")
        return jsonify(new_sch.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        # current_app.logger.error(f"Eroare la adaugarea programului: {e}")
        return jsonify({'Eroare': str(e)}), 500

@schedules_bp.route('/<int:doctor_id>/schedule/<int:schedule_id>', methods=['DELETE'])
@require_auth
def delete_schedule_slot(doctor_id, schedule_id):
    """
    Stergerea programului de lucru in functie de id de catre ADMIN SAU DOCTORUL INSUSI
    """

    # ------- verific daca are permisiunile necesare sa faca operatiunea---------
    token = get_token_from_header()
    user_info = get_user_info_from_token(token)
    external_id = user_info.get('external_id')

    # i-au userul din BD
    user = User.query.filter_by(external_id=external_id).first()
    if not user:
        return jsonify({'Eroare': 'Utilizator necunoscut'}), 404
    
    is_admin = False
    if user.role == UserRole.ADMIN:
        is_admin = True

    is_doctor = False
    if user.role == UserRole.DOCTOR:
        doctor = Doctor.query.filter_by(user_id=user.id).first()
        if doctor and doctor.id == doctor_id:
            is_doctor = True

    # daca nu e nici una eroare
    if not (is_admin or is_doctor):
        return jsonify({'Eroare': 'Permisiuni insuficiente. Doar ADMIN sau doctorul INSUSI pot sterge intervale'}), 403

    # caut programul
    slot = Schedule.query.filter_by(id=schedule_id, doctor_id=doctor_id).first()
    if not slot:
        return jsonify({'Eroare': 'Interval nu exista'}), 404

    try:
        db.session.delete(slot)
        db.session.commit()

        # current_app.logger.info(f"Programul {schedule_id} a fost sters de catre user-ul {user.id}")
        return jsonify({'message': 'Interval sters cu succes'}), 200

    except Exception as e:
        db.session.rollback()
        # current_app.logger.error(f"Eroare la stergerea programului: {e}")
        return jsonify({'Eroare': str(e)}), 500


@schedules_bp.route('/<int:doctor_id>/available-slots', methods=['GET'])
def get_available_slots(doctor_id):
    """
    Calculez sloturile libere pentru o data specifica, cand are doctorul program
    Prima data se determina in ce zi a saptamanii cade data ceruta,
    dupa ia programul doctorului pentru ziua respectiva,
    apoi ia programarile existente din acea zi,
    si la final genereaza sloturile disponibile eliminandu-le pe cele ocupate
    """

    date_str = request.args.get('date')
    if not date_str:
        return jsonify({'Eroare': 'Este nevoie sa introduceti o data available-slots?date=... \nData trebuie sa aiba formatul (YYYY-MM-DD)'}), 400

    try:
        data_ceruta = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'Eroare': 'Format invalid'}), 400

    #ziua
    weekday = data_ceruta.weekday()

    # programele de lucru ale doctorului pentru ziua respectiva
    program = Schedule.query.filter_by(doctor_id=doctor_id, weekday=weekday).all()
    # comanda realizata cu succes chiar daca nu are program in ziua respectiva
    if not program:
        return jsonify({
            'doctor_id': doctor_id,
            'date': date_str,
            'message': 'Doctorul nu lucreaza in aceasta zi',
            'slots': []}), 200

    # programarile existente CONFIRMED sau PENDING pentru ziua respectiva
    start_of_day = datetime.combine(data_ceruta, datetime.min.time())
    end_of_day = datetime.combine(data_ceruta, datetime.max.time())
    
    appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.start_time >= start_of_day,
        Appointment.start_time <= end_of_day,
        Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.REJECTED])
    ).all()

    intervale_ocupate = []
    for app in appointments:
        intervale_ocupate.append((app.start_time, app.end_time))

    # generarea sloturilor disponibile
    intervale_disponibile = []

    for p in program:
        durata = timedelta(minutes=p.slot_duration_minutes)
        timpul_curent = datetime.combine(data_ceruta, p.start_time)
        sf_program = datetime.combine(data_ceruta, p.end_time)

        while timpul_curent + durata <= sf_program:
            slot_start = timpul_curent
            slot_end = timpul_curent + durata

            # verificam daca slotul se suprapune cu vreunul ocupat
            ocupat = False
            for ocupat_start, ocupat_end in intervale_ocupate:
                # StartSlotCurr < endSlotOcupat si EndSlotCurr > StartSlotOcupat => OCUPAT
                if slot_start < ocupat_end and slot_end > ocupat_start:
                    ocupat = True
                    break

            if not ocupat:
                intervale_disponibile.append({'start_time': slot_start.strftime('%H:%M'), 
                                              'end_time': slot_end.strftime('%H:%M')})
            timpul_curent += durata

    return jsonify({'doctor_id': doctor_id, 'date': date_str, 'total_slots': len(intervale_disponibile),'slots': intervale_disponibile}), 200