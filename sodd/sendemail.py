from smtplib import SMTP
from email.mime.text import MIMEText

def sendemail(from_, to, subject, content):

    msg = MIMEText(content, _charset='utf-8')
    msg['Subject'] = subject
    msg['From'] = from_
    msg['To'] = to

    email_server = SMTP('smtp')
    email_server.sendmail(from_, to, msg.as_string())
    email_server.quit()
