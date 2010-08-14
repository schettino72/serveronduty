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
    msg = MIMEText(content, _charset='utf-8')
    msg['Subject'] = subject
    msg['From'] = from_
    assert type(to) is list
    assert type(cc) is list
    msg['To'] = ",".join(to)
    msg['Cc'] = ",".join(cc)

    email_is_sent = False
    try:
        email_server = SMTP('smtp')
        try:
            email_server.sendmail(from_, to + cc, msg.as_string())
            email_is_sent = True
        except:
            logging.error("*** Failed to send the email")
        email_server.quit()
    except:
        logging.error("*** Can't connect to the SMTP server")

    return email_is_sent



#### sample of email SOD integration result content
    # # send email
    # if 'email_from' in application.config and 'email_to' in application.config:
    #     subject = '[ServerOnDuty] r%s (%s) -- %s' % \
    #         (integration.version, integration.owner, integration.result)

    #     lines = []
    #     integration_url = "%s/integration/%s"
    #     lines.append(integration_url % (application.config['websod'],
    #                                     integration.id))

    #     lines.append('\nrevision: %s' % integration.version)
    #     lines.append('owner: %s' % integration.owner)
    #     lines.append('result: %s' % integration.result)
    #     lines.append('comments: %s' % integration.comment)
    #     lines.append('')
    #     lines.append('-' * 40)
    #     lines.append('')

    #     # FIXME: DRY it
    #     new_f_lines = []
    #     for job in integration.failures:
    #         if job.new_failure:
    #             new_f_lines.append("  - %s" % job.name)
    #     if new_f_lines:
    #         lines.append("New failures:")
    #         lines.extend(new_f_lines)

    #     known_f_lines = []
    #     for job in integration.failures:
    #         if not job.new_failure:
    #             known_f_lines.append("  - %s" % job.name)
    #     if known_f_lines:
    #         lines.append("Known failures:")
    #         lines.extend(known_f_lines)

    #     if integration.fixed_failures:
    #         lines.append("Fixed failures:")
    #         for job in integration.fixed_failures:
    #             lines.append("  - %s" % job.name)
    #         lines.append("")

    #     if integration.unstables:
    #         lines.append("Unstable:")
    #         for job in integration.unstables:
    #             lines.append("  - %s" % job.name)
    #         lines.append("")

    #     content = "\n".join(lines)

    #     send_email(application.config['email_from'],
    #                application.config['email_to'],
    #                subject, content)


