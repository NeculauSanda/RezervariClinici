from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from enum import Enum

# initializare ORM SQLAlchemy
db = SQLAlchemy()

class UserRole(str, Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"

class AppointmentStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"

class EventType(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    CANCELLED = "CANCELLED"
    REMINDER_DUE = "REMINDER_DUE"
    PDF_GENERATED = "PDF_GENERATED"

class NotificationType(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"

class NotificationStatus(str, Enum):
    SENT = "SENT"
    FAILED = "FAILED"
    PENDING = "PENDING"

# ------------ modelele -----------

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    external_id = db.Column(db.String(255), unique=True, nullable=False, index=True)  # Keycloak ID (UUID)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    role = db.Column(db.Enum(UserRole), default=UserRole.PATIENT, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # relatii
    # userul poate avea mai multe programari + notificari
    appointments_patient = db.relationship('Appointment', foreign_keys='Appointment.patient_id', backref='patient',
                                             lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    
    # dictionar JSON
    def to_dict(self):
        return {
            'id': self.id,
            'external_id': self.external_id,
            'email': self.email,
            'full_name': self.full_name,
            'phone': self.phone,
            'role': self.role.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f'<User {self.email}>'


class Specialization(db.Model):
    __tablename__ = 'specializations'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)

    # mai multi medici pot avea aceeasi specializare
    doctors = db.relationship('Doctor', backref='specialization', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }


class Cabinet(db.Model):
    __tablename__ = 'cabinets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    floor = db.Column(db.Integer)
    location = db.Column(db.String(255))

    # mai multi medici si programari pot fi asociate unui cabinet
    doctors = db.relationship('Doctor', backref='cabinet', lazy='dynamic')
    appointments = db.relationship('Appointment', backref='cabinet', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'floor': self.floor,
            'location': self.location
        }


class Doctor(db.Model):
    __tablename__ = 'doctors'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    specialization_id = db.Column(db.Integer, db.ForeignKey('specializations.id'), nullable=False)
    cabinet_id = db.Column(db.Integer, db.ForeignKey('cabinets.id'))
    bio = db.Column(db.Text)
    years_experience = db.Column(db.Integer)

    # mai multe programari pot fi asociate unui doctor (daca sterg doctorul, ii sterg si programarile prin cascade)
    user = db.relationship('User', backref=db.backref('doctor_profile', uselist=False))
    schedules = db.relationship('Schedule', backref='doctor', lazy='dynamic', cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='doctor', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'user': self.user.to_dict() if self.user else None,
            'specialization': self.specialization.to_dict() if self.specialization else None,
            'cabinet': self.cabinet.to_dict() if self.cabinet else None,
            'bio': self.bio,
            'years_experience': self.years_experience
        }


class Schedule(db.Model):
    __tablename__ = 'schedules'

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)  # 0 = Luni, 6 = duminica
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_duration_minutes = db.Column(db.Integer, default=30)

    # verificam ca weekday sa fie intre 0 si 6
    __table_args__ = (
        db.CheckConstraint('weekday >= 0 AND weekday <= 6', name='valid_weekday'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'doctor_id': self.doctor_id,
            'weekday': self.weekday,
            'start_time': self.start_time.strftime('%H:%M'),
            'end_time': self.end_time.strftime('%H:%M'),
            'slot_duration_minutes': self.slot_duration_minutes
        }


class Appointment(db.Model):
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    cabinet_id = db.Column(db.Integer, db.ForeignKey('cabinets.id'))
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum(AppointmentStatus), default=AppointmentStatus.PENDING, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # daca sterg o programare, sterg si evenimentele asociate prin cascade
    events = db.relationship('AppointmentEvent', backref='appointment', lazy='dynamic', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='appointment', lazy='dynamic')
    
    def to_dict(self):
        return {
            'id': self.id,
            'patient': self.patient.to_dict() if self.patient else None,
            'doctor': self.doctor.to_dict() if self.doctor else None,
            'cabinet': self.cabinet.to_dict() if self.cabinet else None,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'status': self.status.value,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class AppointmentEvent(db.Model):
    __tablename__ = 'appointment_events'

    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False)
    event_type = db.Column(db.Enum(EventType), nullable=False)
    payload = db.Column(db.JSON)
    is_processed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'appointment_id': self.appointment_id,
            'event_type': self.event_type.value,
            'payload': self.payload,
            'is_processed': self.is_processed,
            'created_at': self.created_at.isoformat()
        }


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'))
    type = db.Column(db.Enum(NotificationType), default=NotificationType.EMAIL, nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'appointment_id': self.appointment_id,
            'type': self.type.value,
            'message': self.message,
            'status': self.status.value,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat()
        }