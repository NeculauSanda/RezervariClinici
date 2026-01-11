from flask import Blueprint, jsonify, request
from bd_struc_flask import db, AppointmentEvent
from datetime import datetime
from utils.auth import require_auth, require_role, get_token_from_header, get_user_info_from_token

events_bp = Blueprint('events', __name__, url_prefix='/events')

@events_bp.route('/pending', methods=['GET'])
@require_role('ADMIN')
def get_pending_events():
    """
    Pentru audit, afiseaza toate evenimentele produse, dar neprocesate
    (adica adminul nu le-a luat in evidenta) inca
    """

    evenimente = AppointmentEvent.query.filter_by(is_processed=False).all()
    return jsonify([e.to_dict() for e in evenimente]), 200

@events_bp.route('/<int:id>/processed', methods=['PUT'])
@require_role('ADMIN')
def mark_event_processed(id):
    """
    Adminul marcheaza ca procesat un eveniment dupa ce vede
    ca notificarea sau actiunea a fost realizata cu succes
    Astea 2 functii sunt mai mult pentru validare si audit
    """

    eveniment = AppointmentEvent.query.get(id)
    if not eveniment:
        return jsonify({'Eroare': 'Eveniment inexistent'}), 404

    try:
        eveniment.is_processed = True
        db.session.commit()
        return jsonify({'mesaj': 'Eveniment procesat'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': str(e)}), 500