from werkzeug import redirect, Response
from werkzeug.exceptions import NotFound

from websod.utils import session, expose, serve_template, application
from websod.models import Integration, Job, SourceTreeRoot, JobGroup, IntegrationResult
from websod.sendemail import send_email


# @expose('/')
# def home(request):
#     # show results from last 3 days
#     integrations_from = datetime.now() + timedelta(days=-3)
#     from_str = integrations_from.strftime("%Y-%m-%d 00:00:00")
#     latest_integrations = session.query(Integration).\
#         filter("started > '%s'" % from_str).\
#         order_by(Integration.started.desc()).all()
#     return serve_template('home.html')


# just show some dictionary on browser for debugging purpose
@expose('/debug')
def debug(request):
    from pprint import pformat
    data = application.config
    return Response(pformat(data))



@expose('/')
def home(request):
    """shows integrations time graph and latest integrations with diff """
    limit = request.args.get('limit')
    if limit and limit.isdigit():
        limit = int(limit)
    else:
        limit = 50
    integrations = session.query(Integration).order_by(Integration.id.desc()).limit(limit).all()
    integrations_view(integrations)
    return serve_template('integration_list.html', integrations=integrations,
                          history=Integration.get_elapsed_history())


@expose('/integration/')
def integration_list(request):
    """shows all integrations with diff """
    integrations = session.query(Integration).order_by(Integration.id.desc()).all()
    integrations_view(integrations)
    return serve_template('integration_list.html', integrations=integrations,
                          history='')


def integrations_view(integrations):
    """process integrations adding necessary info to be used on templates"""
    # calculate integration result
    for integration in integrations:
        try:
            calculate_result(integration)
        except Integration.IntegrationException, exception:
            pass # not finished or  already calculated, go on

        # get elapsed time
        # FIXME - add elapsed time to integration result...
        if integration.state == 'finished':
            integration.elapsed_time = '%.2f' % (integration.getElapsedTime() / 60.0)
            calculate_diff(integration)
        else:
            integration.elapsed_time = ""

    # put diff values into integration object
    for integration in integrations:
        get_diff(integration)
    session.commit()


def get_diff(integration):
    """set diff lists on integration object
    there are 3 lists:
      * failures
      * fixed_failures
      * unstables
    """
    # skip diff calculation if integration not finished
    if integration.state != 'finished':
        # no need calculate for running tasks since the results are not live.
        integration.unstables = []
        integration.failures = []
        integration.fixed_failures = []
        return

    result = integration.integration_result

    # ids are stored in DB as comma separated string
    new_failure_ids = result.new_failures.split(',')
    fix_failure_ids = result.fixed_failures.split(',')
    unstable_ids = result.unstables.split(',')
    failure_ids = result.all_failures.split(',')

    # convert the string to a list of integers
    new_failure_ids = [] if new_failure_ids == [''] else map(int, new_failure_ids)
    fix_failure_ids = [] if fix_failure_ids == [''] else map(int, fix_failure_ids)
    unstable_ids = [] if unstable_ids == [''] else map(int, unstable_ids)
    failure_ids = [] if failure_ids == [''] else map(int, failure_ids)

    def job(job_id):
        return session.query(Job).get(job_id)

    # TODO put results in a dict instead of using integration object
    integration.failures = [job(id_) for id_ in failure_ids]
    integration.unstables = [job(id_) for id_ in unstable_ids]
    integration.fixed_failures = [job(id_) for id_ in fix_failure_ids]
    # mark new failures
    for failure in integration.failures:
        failure.new_failure = failure.id in new_failure_ids


def calculate_diff(integration):
    """Calcualte diff from integration
    results is save on integration_result table
    """
    # TODO this logic can not handle integrations with a higher revision
    # number being executed before a previous revision

    # check if calculated already
    if getattr(integration, 'integration_result', None):
        return

    # classify jobs by result
    unstables = integration.getJobsByResult("unstable")
    failures = integration.getJobsByResult('fail')
    failure_ids = [failure.id for failure in failures]
    unstable_ids = [unstable.id for unstable in unstables]
    # calculate diff
    parent = session.query(Integration).order_by(Integration.id.desc()).\
        filter("id < %d" % integration.id).first()
    if parent is None:
        # nothing to compare on first ever integration
        new_failure_ids = failure_ids
        fix_failure_ids = []
    else:
        new_failure_ids, fix_failure_ids = _compare_integration_failures(
            integration, parent)
    # put into DB
    integration.integration_result = IntegrationResult(
        new_failures=','.join(map(str, new_failure_ids)),
        all_failures=','.join(map(str, failure_ids)),
        fixed_failures=','.join(map(str, fix_failure_ids)),
        unstables=','.join(map(str, unstable_ids)))


def _compare_integration_failures(new_integ, old_integ):
    # job.log is not included in comparsion since the error log contain
    # file path which is different between revisions.
    _get_job_info = lambda job: (job.name, job.type, job.state)

    new_failure_ids = []
    fixed_failure_ids = []

    old_jobs = {}
    for job in old_integ.getJobs():
        old_jobs[_get_job_info(job)] = job

    for new_job in new_integ.getJobs():
        job_info = _get_job_info(new_job)
        if job_info in old_jobs:
            old_job = old_jobs.pop(job_info)
            # compare
            if new_job.result == 'fail' and old_job.result == 'success':
                new_failure_ids.append(new_job.id)
            elif new_job.result == 'success' and old_job.result == 'fail':
                fixed_failure_ids.append(old_job.id)
        elif new_job.result == 'fail':
            # for new added jobs, check 'failures'
            new_failure_ids.append(new_job.id)

    return new_failure_ids, fixed_failure_ids


def calculate_result(integration):
    """check if all job_groups from this integration terminated"""
    if integration.result == 'finished':
        msg = "Already calcualted integration id:%s" % integration.id
        raise Integration.AlreadyCalcualted(msg)

    # calculate only if integration finished,
    # every job_group has an entry where state=='finished'
    num_job_groups = len(application.config['tasks'])
    num_created = len(integration.jobgroups)
    # check all job_groups were created/started
    if num_created != num_job_groups:
        raise Integration.NotFinished('Not ready %d/%d job_group created' %
                                      (num_created, num_job_groups))
    # check all finished
    for job_group in integration.jobgroups:
        if job_group.state != 'finished':
            raise Integration.NotFinished('JobGroup "%s" still running.' %
                                          job_group.id)

    # integration really finished, calculate result
    integration.state = 'finished'
    for job_group in integration.jobgroups:
        if job_group.result != 'success':
            integration.result = 'fail'
            break
    else:
        integration.result = 'success'
    return integration.result



@expose('/integration/<int:id>')
def integration(request, id):
    """integration page just show list of jobs with their result"""
    integration = session.query(Integration).get(id)
    # collect the failed jobs
    failed_jobs = integration.getJobsByResult("fail")
    unstable_jobs = integration.getJobsByResult("unstable")
    success_jobs = integration.getJobsByResult("success")

    return serve_template('integration.html', integration=integration,
            failed_jobs=sorted(failed_jobs, key=lambda k: k.name),
            unstable_jobs=sorted(unstable_jobs, key=lambda k: k.name),
            success_jobs=sorted(success_jobs, key=lambda k: k.name),
                          )



@expose('/job/<int:id>')
def job(request, id):
    the_job = session.query(Job).get(id)
    elapsed_history = the_job.get_elapsed_history()
    return serve_template('job.html', job=the_job, history=elapsed_history)




# this is supposed to be called by sodd's to notify when a job_group is done
@expose('/group_finished/<int:integration_id>')
def group_finished(request, integration_id):
    integration = session.query(Integration).get(integration_id)
    try:
        calculate_result(integration)
        calculate_diff(integration)
    except Integration.IntegrationException, exception:
        return Response(str(exception))
    session.commit()

    get_diff(integration)

    # send email
    if 'email_from' in application.config and 'email_to' in application.config:
        subject = '[ServerOnDuty] r%s (%s) -- %s' % \
            (integration.version, integration.owner, integration.result)

        lines = []
        integration_url = "%s/integration/%s"
        lines.append(integration_url % (application.config['websod'],
                                        integration.id))

        lines.append('\nrevision: %s' % integration.version)
        lines.append('owner: %s' % integration.owner)
        lines.append('result: %s' % integration.result)
        lines.append('comments: %s' % integration.comment)
        lines.append('')
        lines.append('-' * 40)
        lines.append('')

        # FIXME: DRY it
        new_f_lines = []
        for job in integration.failures:
            if job.new_failure:
                new_f_lines.append("  - %s" % job.name)
        if new_f_lines:
            lines.append("New failures:")
            lines.extend(new_f_lines)

        known_f_lines = []
        for job in integration.failures:
            if not job.new_failure:
                known_f_lines.append("  - %s" % job.name)
        if known_f_lines:
            lines.append("Known failures:")
            lines.extend(known_f_lines)

        if integration.fixed_failures:
            lines.append("Fixed failures:")
            for job in integration.fixed_failures:
                lines.append("  - %s" % job.name)
            lines.append("")

        if integration.unstables:
            lines.append("Unstable:")
            for job in integration.unstables:
                lines.append("  - %s" % job.name)
            lines.append("")

        content = "\n".join(lines)

        send_email(application.config['email_from'],
                   application.config['email_to'],
                   subject, content)

    return Response(integration.result)

