from flask import Blueprint, request, jsonify, current_app
from bd_struc_flask import db, Notification, NotificationType, NotificationStatus, User, Appointment
from utils.auth import require_auth, require_role, get_token_from_header, get_user_info_from_token
from utils.email_handler import send_email_smtp
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__, url_prefix='/notifications')

@notifications_bp.route('/send', methods=['POST'])
@require_role('ADMIN')
def send_manual_notification():
    """
    Adminul poate trimite mailuri manual catre un user specific
    """
    data = request.get_json()
    
    for i in ('user_id', 'message', 'type'):
        if i not in data:
            return jsonify({'Eroare': f'Date incomplete trebuie (user_id, message, type(EMAIL), appointment_id(optional))'}), 400

    # verific daca userul exista in BD
    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'Eroare': 'User inexistent'}), 404

    # salvez notificarea in BD ca sa pot sa o vad in istoric
    notificare = Notification(
        user_id=user.id,
        appointment_id=data.get('appointment_id'),
        type=NotificationType[data['type'].upper()],
        message=data['message'],
        status=NotificationStatus.PENDING
    )
    db.session.add(notificare)

    # nu trimit niciun pdf
    pdf_bytes = None
    pdf_name = None

    # trimit emailului
    trimis = False
    if notificare.type == NotificationType.EMAIL:
        trimis = send_email_smtp(user.email, "Notificare Clinica", notificare.message, attachment_data=pdf_bytes, attachment_name=pdf_name)
    
    # daca s-a trimis actualizam statusul din pending in BD ca SENT/FAILED
    if trimis:
        notificare.status = NotificationStatus.SENT
        notificare.sent_at = datetime.utcnow()
    else:
        notificare.status = NotificationStatus.FAILED

    try:
        db.session.commit()
        return jsonify(notificare.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'Eroare': str(e)}), 500


@notifications_bp.route('/user/<int:user_id>', methods=['GET'])
@require_role('ADMIN')
def get_user_notifications(user_id):
    """
    Lista cu mailurile trimise unui user
    """
    
    notificari = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()
    rez = []
    for n in notificari:
        rez.append(n.to_dict())

    return jsonify(rez), 200

@notifications_bp.route('/appointment/<int:app_id>', methods=['GET'])
@require_role('ADMIN')
def get_appointment_notifications(app_id):
    """
    Returneaza toate emailurile trimise pentru o programare data
    """
    notificari = Notification.query.filter_by(appointment_id=app_id).all()
    rez = []
    for n in notificari:
        rez.append(n.to_dict())

    return jsonify(rez), 200