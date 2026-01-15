from fpdf import FPDF
from bd_struc_flask import db, Appointment, Cabinet, Doctor, User
from datetime import datetime

def generate_confirmation_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)


    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"CONFIRMARE PROGRAMARE SLOT - ID.{data.get('appointment_id', 'N/A')}", ln=1, align='C')
    pdf.ln(10)

    # detalii programare
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 8, txt=f"Nume pacient: {data.get('patient_name', 'N/A')}", ln=1)
    pdf.cell(200, 8, txt=f"Email pacient: {data.get('patient_email', 'N/A')}", ln=1)
    pdf.ln(5)

    info_doctor = Doctor.query.get(data.get('doctor_id'))
    info_user_doctor = User.query.get(info_doctor.user_id) if info_doctor else None
    info_specializare = info_doctor.specialization if info_doctor else None
    if info_doctor:
        pdf.cell(200, 8, txt=f"Doctor: Dr. {info_user_doctor.full_name} ({info_specializare.name})", ln=1)

    info_cabinet = Cabinet.query.get(data.get('cabinet_id'))
    if info_cabinet:
        pdf.cell(200, 8, txt=f"Cabinet: {info_cabinet.name}, Locatie: {info_cabinet.location}", ln=1)
        pdf.ln(5)

    #  setare culoare
    pdf.set_text_color(0, 102, 204)  # albastru
    pdf.cell(200, 10, txt=f"Data si ora la care incepe programarea: {data.get('start_time', 'N/A')}", ln=1)
    pdf.cell(200, 10, txt=f"Data si ora la care se termina programarea: {data.get('end_time', 'N/A')}", ln=1)
    pdf.set_text_color(0, 0, 0)

    # status
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"Status: {data.get('status', 'CONFIRMAT')}", ln=1)

    # info
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, txt="Va rugam sa prezentati acest document la asistenta odata ce ajungeti la cabinet pentru a anunta medicul.\n ", ln=1, align='C')
    pdf.cell(200, 10, txt="Multumim ca ati ales clinica noastra!", ln=1, align='C')

    # footer - data la care s-a generat PDF-ul
    pdf.set_y(265)
    pdf.set_font("Arial", size=8)
    pdf.cell(200, 10, txt=f"Document generat la data de: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}", align='C')

    # Returneaza continutul ca bytes string
    return pdf.output(dest='S').encode('latin-1')