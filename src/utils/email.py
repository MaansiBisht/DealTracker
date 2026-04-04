import smtplib
from email.mime.text import MIMEText
from ..config import EMAIL_ADDRESS, EMAIL_PASSWORD


def send_email(subject, body, recipient_email):
    sender_email = EMAIL_ADDRESS
    app_password = EMAIL_PASSWORD

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = recipient_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, app_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
    print(f"Alert email sent to {recipient_email}")
