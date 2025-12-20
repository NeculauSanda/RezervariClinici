from functools import wraps
from flask import request, jsonify, current_app
from jwt.algorithms import RSAAlgorithm
import jwt
import json
import requests

public_key_dict = {}

def get_keycloak_public_key():
    """
    obtin cheia publica de la Keycloak pentru a verifica token-urile userilor
    """
    keycloak_url = current_app.config.get('KEYCLOAK_URL', 'http://keycloak:8080')
    realm = current_app.config.get('KEYCLOAK_REALM', 'master')
    cache_k = f"{keycloak_url}:{realm}"

    # verific in dictionar daca am cheia deja pt a nu o cere de fiecare data
    # astfel incat apelurile sa dureze mai putin pt useri - pt LATENTA MAI PUTINA
    if cache_k in public_key_dict:
        return public_key_dict[cache_k]

    try:
        # cer cheia pt ca nu o am
        response = requests.get(f"{keycloak_url}/realms/{realm}", timeout=5) 
        response.raise_for_status()

        realm_data = response.json()
        public_key_str = realm_data.get('public_key')

        if not public_key_str:
            current_app.logger.error("Nu s-a gasit cheia publica in Keycloak")
            return None

        # convertesc in format PEM
        public_key_new = f"-----BEGIN PUBLIC KEY-----\n{public_key_str}\n-----END PUBLIC KEY-----"
        public_key_dict[cache_k] = public_key_new

        return public_key_new

    except Exception as e:
        current_app.logger.error(f"Eroare pentru a obtine cheia publica de la Keycloak: {e}")
        return None


def verify_token(token):
    """
    Verifica tokenul -> il imbina cu cheia publica obtinuta de la Keycloak
    pt a vedea daca e valid sau nu
    """
    try:
        # decodam tokenul fara verificare mai intai
        neverificat_t = jwt.decode(token, options={"verify_signature": False})
        current_app.logger.info(f"Token decodat: {neverificat_t}")

        public_key = get_keycloak_public_key() # cheia publica

        if not public_key:
            current_app.logger.warning("Nu exista o cheie publica pentru verificare, tokenul neverificat")
            return neverificat_t

        # verific tokenul, algoritmul e cel dat in config 
        t_decodat = jwt.decode(token, public_key, algorithms=['RS256'], audience=None, options={"verify_aud": False})

        return t_decodat

    except jwt.ExpiredSignatureError:

        current_app.logger.error("Token expirat")
        return None
    
    except jwt.InvalidTokenError as e:

        current_app.logger.error(f"Token invalid: {e}")
        return None


def get_token_from_header():
    """
    Extragem tokenul din hederul HTTP -> arata asa: Bearer token
    """

    header_autentificare = request.headers.get('Authorization')

    if not header_autentificare:
        return None
    
    header_s = header_autentificare.split()

    if len(header_s) != 2 or header_s[0].lower() != 'bearer':
        return None
    
    return header_s[1]

def get_user_info_from_token(token):
    """
    Extrag informatiile userului din token sub forma de dictionar
    """
    if not token:
        return None

    # il verificam
    t_ok = verify_token(token)

    if not t_ok:
        return None

    return {
        'external_id': t_ok.get('sub'),
        'email': t_ok.get('email', ''),
        'full_name': t_ok.get('name', ''),
        'roles': t_ok.get('realm_access', {}).get('roles', [])
    }


def require_auth(f):
    """
    Decorator: este nevoie sa fie autentificat pt a apela anumite cereri( cum ar fi profilul)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):

        token = get_token_from_header()

        if not token:
            return jsonify({'Eroare': 'Nu exista token'}), 401
        
        user_info = get_user_info_from_token(token)

        if not user_info:
            return jsonify({'Eroare': 'Token invalid sau expirat'}), 401
        
        request.user = user_info # adaugam informatiile userului in request

        return f(*args, **kwargs)
    
    return decorated_function

def require_role(*roluri):
    """
    Decorator:se verifica rolul, pt BD inainte de a permite accesul la o ruta
    important pentru ADMIN
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # structura User ului
            from bd_struc_flask import User

            # extragem tokenul
            token = get_token_from_header() 

            if not token:
                return jsonify({'Eroare': 'Nu exista token'}), 401

            # extragem info user daca tokenul e valid
            user_info = get_user_info_from_token(token)

            if not user_info:
                return jsonify({'Eroare': 'Token invalid sau expirat'}), 401

            # verificam rolul din BD
            external_id = user_info.get('external_id')
            user = User.query.filter_by(external_id=external_id).first()

            if not user:
                return jsonify({'Eroare': 'Nu exista utilizatorul in BD'}), 404

            roluri_cerute = []
            for r in roluri:
                roluri_cerute.append(r.upper())

            rol_user = user.role.value.upper()
            
            if rol_user not in roluri_cerute:
                return jsonify({'Eroare': 'Permisiuni insuficiente'}), 403

            request.user = user_info # adaugam info user in request
            return f(*args, **kwargs)

        return decorated_function

    return decorator