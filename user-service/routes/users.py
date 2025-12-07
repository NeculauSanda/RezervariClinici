from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from bd_struc_flask import db, User, UserRole
from utils.auth import require_auth, require_role, get_user_info_from_token, get_token_from_header
import requests
import os

users_bp = Blueprint('users', __name__, url_prefix='/users')

# pentru verificare serviciului daca e in picioare
@users_bp.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'OK'}), 200

# ------------------- FUNCTII AJUTATOARE PT KEYCLOAK ----------------

def get_keycloak_admin_token():
    """
    Obtin tokenul de la ADMIN ca sa pot sa inregistrez un nou user in Keycloak
    """
    # la mine adminul e in realm-ul master
    keycloak_url = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
    url = f"{keycloak_url}/realms/master/protocol/openid-connect/token"

    payload = {
        'client_id': 'admin-cli',
        'username': os.getenv('KEYCLOAK_ADMIN', 'admin'),
        'password': os.getenv('KEYCLOAK_ADMIN_PASSWORD', 'admin'),
        'grant_type': 'password'
    }

    try:
        raspuns = requests.post(url, data=payload)
        raspuns.raise_for_status()
        return raspuns.json().get('access_token')

    except Exception as e:
        current_app.logger.error(f"Eroare nu s-a putut obtine tokenul de admin: {e}")
        return None

def update_keycloak_user(external_id, keycloak_data):
    """
    Actualizez datele utilizatorului si in Keycloak
    """
    try:
        admin_token = get_keycloak_admin_token()
        if not admin_token:
            return False

        keycloak_url = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
        realm = os.getenv('KEYCLOAK_REALM', 'medical-clinica')

        url = f"{keycloak_url}/admin/realms/{realm}/users/{external_id}"
        headers = {'Authorization': f'Bearer {admin_token}', 'Content-Type': 'application/json'}

        response = requests.put(url, json=keycloak_data, headers=headers)
        return response.status_code in [200, 204]

    except Exception as e:
        current_app.logger.error(f"Eroare la actualizare Keycloak: {e}")
        return False

def update_keycloak_role(external_id, new_role):
    """
    Actualizez rolul utilizatorului si in Keycloak
    """
    try:
        admin_token = get_keycloak_admin_token()
        if not admin_token:
            return False

        keycloak_url = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
        realm = os.getenv('KEYCLOAK_REALM', 'medical-clinica')

        # obtin rolul actual din Keycloak
        roles_url = f"{keycloak_url}/admin/realms/{realm}/roles"
        headers = {'Authorization': f'Bearer {admin_token}'}

        role_response = requests.get(f"{roles_url}/{new_role}", headers=headers)
        if role_response.status_code != 200:
            return False

        role_data = role_response.json()

        # sterg rolul existent si pun pe cel nou
        user_roles_url = f"{keycloak_url}/admin/realms/{realm}/users/{external_id}/role-mappings/realm"
        requests.delete(user_roles_url, headers=headers)
        requests.post(user_roles_url, headers=headers, json=[role_data])

        return True
    
    except Exception as e:
        current_app.logger.error(f"Eroare la actualizare Keycloak rol: {e}")
        return False

def assign_keycloak_role(external_id, role_name):
    """
    Asigneaza un rol utilizatorului in Keycloak
    """
    try:
        admin_token = get_keycloak_admin_token()
        if not admin_token:
            return False

        keycloak_url = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
        realm = os.getenv('KEYCLOAK_REALM', 'medical-clinica')

        # otin rolul din Keycloak
        roles_url = f"{keycloak_url}/admin/realms/{realm}/roles"
        headers = {'Authorization': f'Bearer {admin_token}'}

        role_response = requests.get(f"{roles_url}/{role_name}", headers=headers)
        if role_response.status_code != 200:
            return False

        role_data = role_response.json()

        # aigneaza rolul userului
        user_roles_url = f"{keycloak_url}/admin/realms/{realm}/users/{external_id}/role-mappings/realm"
        response = requests.post(user_roles_url, headers=headers, json=[role_data])

        return response.status_code in [200, 204]

    except Exception as e:
        current_app.logger.error(f"Eroare la asignare rol Keycloak: {e}")
        return False

def delete_keycloak_user(external_id):
    """
    Sterg utilizatorul si din Keycloak
    """
    try:
        admin_token = get_keycloak_admin_token()
        if not admin_token:
            return False

        keycloak_url = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
        realm = os.getenv('KEYCLOAK_REALM', 'medical-clinica')

        url = f"{keycloak_url}/admin/realms/{realm}/users/{external_id}"
        headers = {'Authorization': f'Bearer {admin_token}'}

        response = requests.delete(url, headers=headers)
        return response.status_code in [200, 204]

    except Exception as e:
        current_app.logger.error(f"Eroare la stergere Keycloak: {e}")
        return False

#  ------------------- AUTENTIFICARE NOU UTILIZATOR -------------------

@users_bp.route('/register', methods=['POST'])
def register_user():
    """
    Inregistrez un nou user, (adica isi face un cont nou)
    Se creeaza atat in Keycloak cat si in BD local
    """

    data = request.get_json()

    # date de intrare obligatorii
    required_fields = ['email', 'password', 'full_name']
    if not data or not all(k in data for k in required_fields):
        return jsonify({'Eroare': 'Lipsesc campuri obligatorii (email, password, full_name)'}), 400

    email = data['email']
    password = data['password']
    full_name = data['full_name']
    role_str = data.get('role', 'PATIENT').upper()  # rolul pt user-service este de PACIENT implicit

    # doar pacientii se pot inregistra singuri
    if role_str != 'PATIENT':
        return jsonify({'Eroare': 'Doar pacientii se pot auto-iregistra. Doctorii trebuie creati de admin'}), 403

    # verific daca utilizatorul se afla deja in BD dupa email
    if User.query.filter_by(email=email).first():
        return jsonify({'Eroare': 'Emailul deja exista in BD local'}), 409

    # iau tokenul de admin ca sa pot sa il pun in Keycloak
    admin_token = get_keycloak_admin_token()

    if not admin_token:
        return jsonify({'Eroare': 'Nu s-a putut obtine tokenul de admin (Inregistrarea nu a reusit)'}), 500

    # creez userul il adaugam in realm ul aplicatiei
    keycloak_url = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
    realm = os.getenv('KEYCLOAK_REALM', 'medical-clinica')
    create_url = f"{keycloak_url}/admin/realms/{realm}/users"
    
    # separ numele de prenume
    names = full_name.split(' ', 1)
    first_name = names[0]
    last_name = names[1] if len(names) > 1 else ""

    # username-ul o sa pun emailul ca e unic, iar la mail pun deja ca e verificat si parola e definitiva
    keycloak_user_data = {
        "username": email,
        "email": email,
        "enabled": True,
        "firstName": first_name,
        "lastName": last_name,
        "emailVerified": True,
        "credentials": [{
            "type": "password",
            "value": password,
            "temporary": False
        }],
    }

    headers = {
        'Authorization': f'Bearer {admin_token}',
        'Content-Type': 'application/json'
    }

    response = requests.post(create_url, json=keycloak_user_data, headers=headers)
    
    if response.status_code == 409:
        return jsonify({'Eroare': 'Utilizatorul deja exista in Keycloak'}), 409
    
    # 201 -> userul a fost creat, alte erori
    if response.status_code != 201:
        current_app.logger.error(f"Nu s-a putut crea userul in Keycloak: {response.text}")
        return jsonify({'Eroare': f'Nu s-a putut crea userul in Keycloak: {response.status_code}'}), 500

    # obtin ID(UUID) generat de Keycloak
    # Keycloak returneaza ID-ul in header-ul 'Location' la creare:".../users/UUID"
    # daca nu e acolo, incerc sa caut userul dupa email
    location_header = response.headers.get('Location')
    if location_header:
        keycloak_id = location_header.split('/')[-1]
    else:

        search_url = f"{keycloak_url}/admin/realms/{realm}/users"
        raspuns_search = requests.get(search_url, params={'email': email}, headers=headers)

        if raspuns_search.status_code == 200 and len(raspuns_search.json()) > 0:
            keycloak_id = raspuns_search.json()[0]['id']
        else:
            return jsonify({'Eroare': 'User creat dar nu s-a putut obtine ID-ul'}), 500

    # asignare rol utilizatorului in Keycloak
    assign_keycloak_role(keycloak_id, role_str)

    # salvam userul in BD local
    try:
        # default PACIENT
        role_enum = UserRole.PATIENT

        if role_str == 'DOCTOR':
            role_enum = UserRole.DOCTOR
        elif role_str == 'ADMIN':
            role_enum = UserRole.ADMIN

        new_user = User(
            external_id=keycloak_id,
            email=email,
            full_name=full_name,
            phone=data.get('phone'),
            role=role_enum
        )
        
        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            'message': 'User inregistrat cu succes',
            'id': new_user.id,
            'external_id': new_user.external_id,
            'email': new_user.email
        }), 201

    except Exception as e:
        # daca BD ul pica resetam bd prin rollback
        db.session.rollback()
        current_app.logger.error(f"Eroare BD: {e}")
        return jsonify({'Eroare': 'Eroare la baza de date'}), 500

# ---------------------- COMENZI USER ---------------------

@users_bp.route('/me', methods=['PUT'])
@require_auth
def update_current_user():
    """
    Actualizeaza profilul userului curent (nu poate accesa daca nu e autentificat)
    + actualizare in Keycloak
    """

    external_id = request.user.get('external_id')
    data = request.get_json()

    user = User.query.filter_by(external_id=external_id).first()

    if not user:
        return jsonify({'Eroare': 'Userul nu a fost gasit'}), 404

    # actualizam campurile permise si datele pentru Keycloak
    keycloak_data = {}

    if 'full_name' in data:
        user.full_name = data['full_name']
        names = data['full_name'].split(' ', 1)
        keycloak_data['firstName'] = names[0]
        keycloak_data['lastName'] = names[1] if len(names) > 1 else ""

    if 'phone' in data:
        user.phone = data['phone']

    user.updated_at = datetime.utcnow()

    try:
        # atualizez si in keycloak
        if keycloak_data:
            update_keycloak_user(external_id, keycloak_data)

        # salvam modificarile in BD
        db.session.commit()
        return jsonify(user.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Eroare la actualizarea userului: {e}")
        return jsonify({'Eroare': 'Eroare actualizarea userului la baza de date'}), 500


@users_bp.route('/me', methods=['GET'])
@require_auth
def get_current_user():
    """
    Returneaza profilul userului curent (nu poate accesa daca nu e autentificat)
    """

    external_id = request.user.get('external_id')
    
    user = User.query.filter_by(external_id=external_id).first()

    if not user:
        return jsonify({'Eroare': 'Userul nu a fost gasit'}), 404

    return jsonify(user.to_dict()), 200


@users_bp.route('/sync-keycloak', methods=['POST'])
@require_auth
def sync_keycloak():
    """
    Sincronizeaza BD-ului local cu datele din Keycloak ale userului autentificat
    Daca userul nu exista in BD local, dar se afla doar in Keycloak
    """

    token = get_token_from_header()
    user_info = get_user_info_from_token(token)

    if not user_info:
        return jsonify({'Eroare': 'Token invalid'}), 401

    external_id = user_info.get('external_id')
    email = user_info.get('email')

    if not external_id or not email:
        return jsonify({'Eroare': 'Date token invalide'}), 401

    # verific daca userul exista in BD local
    user = User.query.filter_by(external_id=external_id).first()

    # verific ce rol are
    keycloak_roles = user_info.get('roles', [])
    role = UserRole.PATIENT

    if 'ADMIN' in keycloak_roles:
        role = UserRole.ADMIN
    elif 'DOCTOR' in keycloak_roles:
        role = UserRole.DOCTOR

    # Daca nu exista il adaug, daca exista actualizez datele
    if user:
        # actualizez datele userului existent
        user.email = email
        user.full_name = user_info.get('full_name', user.full_name)
        user.role = role
    else:
        user = User(
            external_id=external_id,
            email=email,
            full_name=user_info.get('full_name', email.split('@')[0]),
            role=role
        )
        db.session.add(user)

    # actualizez data ultimei modificari a contului
    user.updated_at = datetime.utcnow()

    try:
        db.session.commit()
        return jsonify({
            'message': 'Sincronizare reusita a userului',
            'user': user.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Eroare la sincronizarea userului: {e}")
        return jsonify({'Eroare': 'Eroare la sincronizarea userului'}), 500


# -------------------------- ADMIN COMENZI -------------------------

@users_bp.route('/', methods=['GET'])
@require_role('ADMIN')
def get_all_users():
    """
    Lisa utilizatorilor poate doar ADMIN sa afiseze este pus prin require_role
    """

    # cati afisez pe o pagina si ce pagina
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    role = request.args.get('role', None) # optional pt filtrare dupa rol

    query = User.query

    # filtrare dupa rol daca e specificat
    if role:
        try:
            role_enum = UserRole[role.upper()]
            query = query.filter_by(role=role_enum)
        except KeyError:
            return jsonify({'Eroare': 'Rol invalid'}), 400

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'users': [user.to_dict() for user in pagination.items],
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages
    }), 200

@users_bp.route('/<int:user_id>', methods=['GET'])
@require_role('ADMIN')
def get_user(user_id):
    """
    Returneaza info despre user  dupa id(doar ADMIN), daca incearca altcineva nu poate
    """
    user = User.query.get(user_id)

    if not user:
        return jsonify({'Eroare': 'Utilizatorul nu a fost gasit'}), 404

    return jsonify(user.to_dict()), 200


@users_bp.route('/<int:user_id>', methods=['PUT'])
@require_role('ADMIN')
def update_user(user_id):
    """
    Actualizari facute userilor doar de catre admin (cum ar fi rolul, celelalte campuri se pot
    schimba si de catre admin, dar si de catre user) + actualizare in Keycloak
    """
    user = User.query.get(user_id)

    if not user:
        return jsonify({'Eroare': 'Utilizatorul nu a fost gasit'}), 404

    # actualizare atat in BD cat si in Keycloak
    data = request.get_json()
    keycloak_data = {}

    if 'email' in data:
        user.email = data['email']
        keycloak_data['email'] = data['email']

    if 'full_name' in data:
        user.full_name = data['full_name']
        names = data['full_name'].split(' ', 1)
        keycloak_data['firstName'] = names[0]
        keycloak_data['lastName'] = names[1] if len(names) > 1 else ""

    if 'phone' in data:
        user.phone = data['phone']

    # functie separata pt rol
    # if 'role' in data:
    #     try:
    #         user.role = UserRole(data['role'])
    #     except ValueError:
    #         return jsonify({'Eroare': 'Rol invalid'}), 400

    # daca e alt camp eroare ca nu se poate actualiza
    for key in data:
        if key not in ['email', 'full_name', 'phone']:
            return jsonify({'Eroare': f'Campul "{key}" nu poate fi actualizat aici'}), 400

    # actualizez data ultimei modificari a profilului
    user.updated_at = datetime.utcnow()

    # adaugare in BD
    try:
        # actualzez si in keycloak
        if keycloak_data:
            update_keycloak_user(user.external_id, keycloak_data)

        db.session.commit()
        return jsonify(user.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Eroare la actualizarea userului: {e}")
        return jsonify({'Eroare': 'Eroare la actualizarea userului'}), 500


@users_bp.route('/<int:user_id>/role', methods=['PUT'])
@require_role('ADMIN')
def update_user_role(user_id):
    """
    Actualizeaza doar rolul unui utilizator (doar ADMIN) + actualizare in Keycloak
    """
    data = request.get_json()

    if 'role' not in data:
        return jsonify({'Eroare': 'Rolul este obligatoriu'}), 400

    user = User.query.get(user_id)
    if not user:
        return jsonify({'Eroare': 'Utilizatorul nu a fost gasit'}), 404

    try:
        new_role = UserRole[data['role'].upper()]
        user.role = new_role
        # actualizez data ultimei modificari a profilului + bd
        user.updated_at = datetime.utcnow()

        # actualizez si in Keycloak
        update_keycloak_role(user.external_id, data['role'].upper())

        db.session.commit()
        return jsonify(user.to_dict()), 200

    except KeyError:
        return jsonify({'Eroare': 'Rol invalid'}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Eroare la actualizarea rolului: {e}")
        return jsonify({'Eroare': 'Eroare la actualizarea rolului'}), 500


@users_bp.route('/<int:user_id>', methods=['DELETE'])
@require_role('ADMIN')
def delete_user(user_id):
    """
    Stergerea unui user (doar ADMIN)
    """
    user = User.query.get(user_id)
    if not user:
        return jsonify({'Eroare': 'Utilizatorul nu a fost gasit'}), 404

    try:
        external_id = user.external_id

        # sterg in BD
        db.session.delete(user)
        db.session.commit()

        # sterg din Keycloak
        delete_keycloak_user(external_id)

        return jsonify({'message': 'Utilizatorul a fost sters cu succes'}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Eroare la stergerea userului: {e}")
        return jsonify({'Eroare': 'Eroare la stergerea userului'}), 500