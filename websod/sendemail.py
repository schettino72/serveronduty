import logging
from smtplib import SMTP
from email.mime.text import MIMEText

def send_email(from_, to, cc, subject, content):
    """
    @param from_ (str)
    @param to (list - str)
    @param cc (list - str)
    @param content (str)
    """
    if type(to) is list:
        to_str = ', '.join(to)
    if type(cc) is list:
        cc_str = ', '.join(cc)


    msg = MIMEText(content, _charset='utf-8')
    msg['Subject'] = subject
    msg['From'] = from_
    msg['To'] = to_str
    msg['Cc'] = cc_str

    email_is_sent = False
    try:
        email_server = SMTP('smtp')
        try:
            email_server.sendmail(from_, to, msg.as_string())
            email_is_sent = True
        except:
            logging.error("*** Failed to send the email")
        email_server.quit()
    except:
        logging.error("*** Can't connect to the SMTP server")

    return email_is_sent
