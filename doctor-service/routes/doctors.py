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
    Obtin tokenul de la medical-backend care are configurari "asemanatoare" cu cele de ADMIN 
    (realm-admin, manage-users, view-users) pt a actualiza rolurile userilor in Keycloak 
    (este diferit de adminul original)
    """
    try:
        keycloak_url = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
        realm = os.getenv('KEYCLOAK_REALM', 'medical-clinica')
        token_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"

        client_id = os.getenv('KEYCLOAK_BACKEND_CLIENT_ID', 'medical-backend')
        client_secret = os.getenv('KEYCLOAK_BACKEND_CLIENT_SECRET', 'secret-backend')

        raspuns = requests.post(token_url, data={
            'client_id': client_id,
            'client_secret': client_secret,
            'grant_type': 'client_credentials'
        })
        
        if raspuns.status_code == 200:
            return raspuns.json().get('access_token')

        return None

    except Exception as e:
        print(f"Eroare nu s-a putut obtine tokenul de la medical-backend(serv de gestionare): {e}")
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

        # obtin rolul nou
        rol_new = requests.get(f"{roles_url}/{new_role}", headers=headers)

        if rol_new.status_code != 200:
            return False

        role_data = rol_new.json()

        # url pt rolul vechi
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
@require_auth
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
        # Verific daca sunt doctori cu aceasta specializare =>am conflict si trebuie stersi nu am nevoie sa fac asta si 
        # e mult de munca sa i sterg
        doctori = Doctor.query.filter_by(specialization_id=id).all()
        if doctori:
            return jsonify({'Eroare': f'Nu poti sterge aceasta specializare. Sunt {len(doctori)} doctori cu aceasta specializare'}), 409

        db.session.delete(specializare)
        db.session.commit()

        return jsonify({'message': 'Specializarea stearsa cu succes'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': f'Eroare la stergere specializare: {str(e)}'}), 500

# ----------------- COMENZI PENTRU CABINETE -----------------

@aux_bp.route('/cabinets', methods=['GET'])
@require_auth
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
        return jsonify({'Eroare': 'Numele cabinetului este obligatoriu'}), 400

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
        # Verific daca sunt doctori in acest cabinet -=> la fel ca la specializare (nu ma axez pe asta)
        doctori = Doctor.query.filter_by(cabinet_id=id).all()
        if doctori:
            return jsonify({'Eroare': f'Nu poti sterge acest cabinet. Sunt {len(doctori)} doctori in acest cabinet'}), 409

        db.session.delete(cabinet)
        db.session.commit()

        return jsonify({'message': 'Cabinetul sters cu succes'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': f'Eroare la stergere cabinet: {str(e)}'}), 500

# ----------------- COMENZI PENTRU DOCTORI -----------------

@doctors_bp.route('', methods=['GET'])
@require_auth
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

    doctorii = filter_doc.all()

    results = []
    for doc in doctorii:
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
@require_auth
def get_doctor(id):
    """
    Returneaza detaliile unui doctor dupa id
    """
    doc = Doctor.query.get(id)

    if not doc:
        return jsonify({'Eroare': 'Doctorul nu exista'}), 404

    rasp = {
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
    return jsonify(rasp), 200

@doctors_bp.route('', methods=['POST'])
@require_role('ADMIN')
def create_doctor():
    """
    ADMINUL ridica rangul la DOCTOR a unui user existent si ii creeaza profilul de doctor
    Chiar daca are setat rolul de DOCTOR in Keycloak, nu va fi considerat doctor in BD
    pana cand nu are creat profilul de doctor
    """

    data = request.get_json()
    obligatoriu = ['user_id', 'specialization_id', 'cabinet_id']
    for k in obligatoriu:
        if k not in data:
            return jsonify({'Eroare': 'Lipsesc date necesare (user_id, specialization_id, cabinet_id)'}), 400

    #verific daca exista userul
    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'Eroare': 'Userul nu exista'}), 404

    # verific daca are deja profil dedoctor
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

        # actualizez si in Keycloak rolul - userul
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
        # obtin userul asociat doctorului
        user = doc.user

        # schimb rolul la PATIENT automat
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