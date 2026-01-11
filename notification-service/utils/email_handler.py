import smtplib
from email.message import EmailMessage
from flask import current_app

def send_email_smtp(to_email, subiect, body, attachment_data=None, attachment_name="document.pdf"):
    """
    Trimite email folosind serverul SMTP configurat (Mailhog)
    """

    mesaj = EmailMessage()
    mesaj.set_content(body)
    mesaj['Subject'] = subiect
    mesaj['From'] = current_app.config['SMTP_FROM']
    mesaj['To'] = to_email

    # adaug atasament daca exista PDF-ul generat
    if attachment_data:
        mesaj.add_attachment(
            attachment_data,
            maintype='application',
            subtype='pdf',
            filename=attachment_name
        )

    try:
        with smtplib.SMTP(current_app.config['SMTP_HOST'], current_app.config['SMTP_PORT']) as server:
            server.send_message(mesaj)
        print(f"Email trimis cu succes catre {to_email}")
        return True

    except Exception as e:
        print(f"Eroare la trimiterea emailului: {e}")
        return False