from flask import Blueprint, request, jsonify
from bd_struc_flask import db, Doctor, User, Specialization, Cabinet, UserRole
from utils.auth import require_auth, require_role
import os
import requests
from datetime import datetime, timedelta

# rute pt comenezi doctor si cabinete/specializari
doctors_bp = Blueprint('doctors', __name__, url_prefix='/doctors')
aux_bp = Blueprint('auxiliaries', __name__)

# ---------------- FUNCTII AJUTATOARE PENTRU INTERACTIUNEA CU KEYCLOAK  -----------------
def get_keycloak_admin_token():
    """
    Obtin tokenul de la ADMIN ca sa pot sa pot sa actualizez rolurile userilor in Keycloak
    """
    try:
        keycloak_url = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
        token_url = f"{keycloak_url}/realms/master/protocol/openid-connect/token"
        
        response = requests.post(token_url, data={
            'username': 'admin',
            'password': 'admin',
            'grant_type': 'password',
            'client_id': 'admin-cli'
        })
        
        if response.status_code == 200:
            return response.json().get('access_token')
        return None
    except Exception as e:
        print(f"Eroare la obtinere admin token: {e}")
        return None

def update_keycloak_role(user_id, external_id, new_role):
    """
    Actualize rolul in Keycloak pentru un user dat
    """
    try:
        # iau tokenul de admin
        admin_token = get_keycloak_admin_token()
        if not admin_token:
            return False

        keycloak_url = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
        realm = os.getenv('KEYCLOAK_REALM', 'medical-clinica')

        # url pt roluri existente
        roles_url = f"{keycloak_url}/admin/realms/{realm}/roles"

        headers = {'Authorization': f'Bearer {admin_token}'}

        # obtin rolul
        role_response = requests.get(f"{roles_url}/{new_role}", headers=headers)

        if role_response.status_code != 200:
            return False

        role_data = role_response.json()

        # url pt rolurile userului
        user_roles_url = f"{keycloak_url}/admin/realms/{realm}/users/{external_id}/role-mappings/realm"

        # sterg rolul existent
        requests.delete(user_roles_url, headers=headers)

        #pun noul rol
        requests.post(user_roles_url,headers=headers, json=[role_data])

        return True

    except Exception as e:
        print(f"Eroare la actualizare Keycloak: {e}")
        return False

# ----------------- COMENZI SEPARATE PENTRU SPECIALIZARI SI CABINETE -----------------
# ----------------- COMENZI PENTRU SPECIALIZARI -----------------
@aux_bp.route('/specializations', methods=['GET'])
def get_specializations():
    """
    Afiseaza toate specializarile din clinica
    """
    specializari = Specialization.query.all()
    return jsonify([s.to_dict() for s in specializari]), 200

@aux_bp.route('/specializations', methods=['POST'])
@require_role('ADMIN')
def create_specialization():
    """
    Se creeaza o noua specializare doar de catre ADMIN
    """

    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'Eroare': 'Numele specializarii este obligatoriu'}), 400

    # pentru a elimina DUPLICATELE
    exista = Specialization.query.filter_by(name=data['name']).first()
    if exista:
        return jsonify({'Eroare': 'Specializarea exista deja'}), 409

    try:
        new_spec = Specialization(name=data['name'], description=data.get('description', ''))
        db.session.add(new_spec)
        db.session.commit()
        return jsonify(new_spec.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': f'Eroare la crearea specializarii: {str(e)}'}), 500

@aux_bp.route('/specializations/<int:id>', methods=['PUT'])
@require_role('ADMIN')
def update_specialization(id):
    """
    Actualizare specializare existenta - doar ADMIN
    """
    specializare = Specialization.query.get(id)
    if not specializare:
        return jsonify({'Eroare': 'Specializarea nu exista'}), 404

    data = request.get_json()

    if 'name' in data:
        specializare.name = data['name']
    if 'description' in data:
        specializare.description = data['description']

    db.session.commit()
    return jsonify(specializare.to_dict()), 200

@aux_bp.route('/specializations/<int:id>', methods=['DELETE'])
@require_role('ADMIN')
def delete_specialization(id):
    """
    Stergere specializarea  doar ADMIN
    Daca avem doctori la aceasta specializare, nu se poate sterge
    """
    specializare = Specialization.query.get(id)
    if not specializare:
        return jsonify({'Eroare': 'Specializarea nu exista'}), 404

    try:
        # Verific daca sunt doctori cu aceasta specializare
        doctori = Doctor.query.filter_by(specialization_id=id).all()
        if doctori:
            return jsonify({
                'Eroare': f'Nu poti sterge aceasta specializare. Sunt {len(doctori)} doctori cu aceasta specializare',
                'doctori_count': len(doctori)
            }), 409  # Conflict

        db.session.delete(specializare)
        db.session.commit()

        return jsonify({'message': 'Specializarea stearsa cu succes'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': f'Eroare la stergere specializare: {str(e)}'}), 500

# ----------------- COMENZI PENTRU CABINETE -----------------

@aux_bp.route('/cabinets', methods=['GET'])
def get_cabinets():
    """
    Afiseaza toate cabinetele din clinica
    """
    cabinete = Cabinet.query.all()
    return jsonify([c.to_dict() for c in cabinete]), 200

@aux_bp.route('/cabinets', methods=['POST'])
@require_role('ADMIN')
def create_cabinet():
    """
    Se creeaza un nou cabinet in clinica doar de catre ADMIN
    """
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'Eroare': 'Numele cabinetului este obligatoriu', 
                        'exemplu': '''{"name": "Cabinet 6", "floor(opt)": 2, "location(opt)": "Etaj 2, Usa 206"}'''}), 400

    # verific DUPLICATE in BD
    exista = Cabinet.query.filter_by(name=data['name']).first()
    if exista:
        return jsonify({'Eroare': 'Cabinetul exista deja'}), 409

    try:
        new_cab = Cabinet(
            name=data['name'],
            floor=data.get('floor', 0),
            location=data.get('location', '')
        )
        db.session.add(new_cab)
        db.session.commit()
        return jsonify(new_cab.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': f'Eroare la crearea cabinetului: {str(e)}'}), 500

@aux_bp.route('/cabinets/<int:id>', methods=['PUT'])
@require_role('ADMIN')
def update_cabinet(id):
    """
    Actualizare cabinet existent - doar ADMIN
    """
    cabinet = Cabinet.query.get(id)
    if not cabinet:
        return jsonify({'Eroare': 'Cabinetul nu exista'}), 404

    data = request.get_json()

    if 'name' in data:
        cabinet.name = data['name']
    if 'floor' in data:
        cabinet.floor = data['floor']
    if 'location' in data:
        cabinet.location = data['location']
    db.session.commit()
    return jsonify(cabinet.to_dict()), 200

@aux_bp.route('/cabinets/<int:id>', methods=['DELETE'])
@require_role('ADMIN')
def delete_cabinet(id):
    """
    Stergere cabinetul - doar ADMIN
    Daca avem doctori in cabinet, nu se poate sterge
    """
    cabinet = Cabinet.query.get(id)
    if not cabinet:
        return jsonify({'Eroare': 'Cabinetul nu exista'}), 404

    try:
        # Verific daca sunt doctori in acest cabinet
        doctori = Doctor.query.filter_by(cabinet_id=id).all()
        if doctori:
            return jsonify({
                'Eroare': f'Nu poti sterge acest cabinet. Sunt {len(doctori)} doctori in acest cabinet',
                'doctori_count': len(doctori)
            }), 409  # Conflict

        db.session.delete(cabinet)
        db.session.commit()

        return jsonify({'message': 'Cabinetul sters cu succes'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': f'Eroare la stergere cabinet: {str(e)}'}), 500

# ----------------- COMENZI PENTRU DOCTORI -----------------

@doctors_bp.route('', methods=['GET'])
def get_all_doctors():
    """
    Returneaza lista doctorilor,
    Se poate filtra dupa specializare sau cabinet
    """
    spec_id = request.args.get('specialization_id')
    cab_id = request.args.get('cabinet_id')

    filter_doc = Doctor.query
    if spec_id:
        filter_doc = filter_doc.filter_by(specialization_id=spec_id)
    if cab_id:
        filter_doc = filter_doc.filter_by(cabinet_id=cab_id)

    doctors = filter_doc.all()

    # adaug doar numele doctorului in output
    results = []
    for doc in doctors:
        # d_dict = doc.to_dict()
        # if doc.user:
        #     d_dict['full_name'] = doc.user.full_name
        # results.append(d_dict)
        result = {
            'id': doc.id,
            'user_id': doc.user_id,
            'full_name': doc.user.full_name if doc.user else None,
            'email': doc.user.email if doc.user else None,
            'specialization_id': doc.specialization_id,
            'specialization': doc.specialization.to_dict() if doc.specialization else None,
            'cabinet_id': doc.cabinet_id,
            'cabinet': doc.cabinet.to_dict() if doc.cabinet else None,
            'bio': doc.bio,
            'years_experience': doc.years_experience
        }
        results.append(result)

    return jsonify(results), 200

@doctors_bp.route('/<int:id>', methods=['GET'])
def get_doctor(id):
    """
    Returneaza detaliile unui doctor dupa id
    """
    doc = Doctor.query.get(id)
    if not doc:
        return jsonify({'Eroare': 'Doctorul nu exista'}), 404

    resp = {
        'id': doc.id,
        'user_id': doc.user_id,
        'full_name': doc.user.full_name if doc.user else None,
        'email': doc.user.email if doc.user else None,
        'specialization_id': doc.specialization_id,
        'specialization': doc.specialization.to_dict() if doc.specialization else None,
        'cabinet_id': doc.cabinet_id,
        'cabinet': doc.cabinet.to_dict() if doc.cabinet else None,
        'bio': doc.bio,
        'years_experience': doc.years_experience
    }
    return jsonify(resp), 200

@doctors_bp.route('', methods=['POST'])
@require_role('ADMIN')
def create_doctor():
    """
    ADMINUL ridica rangul la DOCTOR a unui user existent si ii creeaza profilul de doctor
    Chiar daca are setat rolul de DOCTOR in Keycloak, nu va fi considerat doctor in BD
    pana cand nu are creat profilul de doctor
    """

    data = request.get_json()
    required = ['user_id', 'specialization_id']
    if not all(k in data for k in required):
        return jsonify({'Eroare': 'Lipsesc date necesare (user_id, specialization_id, cabinet_id)'}), 400

    #verific daca exista userul
    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'Eroare': 'Userul nu exista'}), 404

    # verific daca e deja doctor
    if Doctor.query.filter_by(user_id=user.id).first():
        return jsonify({'Eroare': 'Acest user este deja doctor'}), 409

    # creez profilul de doctor
    try:
        new_doc = Doctor(
            user_id=user.id,
            specialization_id=data['specialization_id'],
            cabinet_id=data.get('cabinet_id'),
            bio=data.get('bio', ''),
            years_experience=data.get('years_experience', 0)
        )

        # ACTUALIZEZ SI ROLUL IN BD LA DOCTOR
        user.role = UserRole.DOCTOR

        # actualizez si in Keycloak rolul - usrul
        update_keycloak_role(user.id, user.external_id, 'DOCTOR')

        db.session.add(new_doc)
        db.session.commit()

        return jsonify({'message': 'Doctor creat cu succes', 'doctor': new_doc.to_dict()}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': str(e)}), 500

@doctors_bp.route('/<int:id>', methods=['PUT'])
@require_role('ADMIN')
def update_doctor(id):
    """
    Actualizare profil unui doctor - doar ADMIN"""
    doc = Doctor.query.get(id)
    if not doc:
        return jsonify({'Eroare': 'Doctorul nu exista'}), 404

    data = request.get_json()

    if 'specialization_id' in data:
        doc.specialization_id = data['specialization_id']
    if 'cabinet_id' in data:
        doc.cabinet_id = data['cabinet_id']
    if 'bio' in data:
        doc.bio = data['bio']
    if 'years_experience' in data:
        doc.years_experience = data['years_experience']
  
    db.session.commit()
    return jsonify(doc.to_dict()), 200

@doctors_bp.route('/<int:id>', methods=['DELETE'])
@require_role('ADMIN')
def delete_doctor(id):
    """
    Stergere profil doctor - doar ADMIN
    Si il retrogradeaza la PATIENT in BD
    """
    doc = Doctor.query.get(id)
    if not doc:
        return jsonify({'Eroare': 'Doctorul nu exista'}), 404

    try:
        # otin userul asociat doctorului
        user = doc.user

        # Retrogradez userul la PATIENT
        if user:
            user.role = UserRole.PATIENT
            # actualizez si in Keycloak rolul la PATIENT
            update_keycloak_role(user.id, user.external_id, 'PATIENT')

        # Sterg profilul doctor
        db.session.delete(doc)
        db.session.commit()

        return jsonify({
            'message': 'Profilul doctorului sters cu succes',
            'user_id': user.id if user else None,
            'new_role': 'PATIENT'
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': f'Eroare la stergere doctor: {str(e)}'}), 500