from smtplib import SMTP
from email.mime.text import MIMEText
from sodd.litemodel import get_failed_job

def send_notify_email(from_, to, integration_id, integration_result,
                                    revision, committer, cursor):
    subject = '[ServerOnDuty] %s @r%s -- %s' % \
                (integration_result, revision, committer)

    content = ''
    if integration_result == 'fail':
        # get (name, result, log) from each failed/unstable job
        result = get_failed_job(cursor, integration_id)
        for each in result:
            content += 'test_name: %s\nresult: %s\n' \
                       'logs:\n\n%s\n\n\n' % each

    send_email(from_, to, subject, content)


def send_email(from_, to, subject, content):
    msg = MIMEText(content, _charset='utf-8')
    msg['Subject'] = subject
    msg['From'] = from_
    msg['To'] = to

    email_server = SMTP('smtp')
    email_server.sendmail(from_, to, msg.as_string())
    email_server.quit()
