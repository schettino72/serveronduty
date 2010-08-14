from flask import render_template, request

from websod import app
from websod.models import Integration, Job
from websod.integration import integrations_view, calculate_result, calculate_diff, get_diff


@app.route('/debug')
def debug():
    from pprint import pformat
    return "<pre>" + pformat(dict(app.config)) + "</pre>"


@app.route('/')
def home():
    """shows integrations time graph and latest integrations with diff """
    session = app.db.session
    limit = request.args.get('limit', 50, int)
    integrations = session.query(Integration).order_by(Integration.id.desc()).limit(limit).all()
    integrations_view(integrations)
    return render_template('integration_list.html', integrations=integrations,
                           history=Integration.get_elapsed_history(session))


@app.route('/integration/')
def integration_list():
    """shows all integrations with diff """
    session = app.db.session
    integrations = session.query(Integration).order_by(Integration.id.desc()).all()
    integrations_view(integrations)
    return render_template('integration_list.html',
                           integrations=integrations,
                           history='')


@app.route('/integration/<int:id_>')
def integration(id_):
    """integration page just show list of jobs with their result"""
    integration = app.db.session.query(Integration).get(id_)
    # collect the failed jobs
    failed_jobs = integration.getJobsByResult("fail")
    unstable_jobs = integration.getJobsByResult("unstable")
    success_jobs = integration.getJobsByResult("success")

    tpl_data = {'integration': integration,
                'failed_jobs': sorted(failed_jobs, key=lambda k: k.name),
                'unstable_jobs': sorted(unstable_jobs, key=lambda k: k.name),
                'success_jobs': sorted(success_jobs, key=lambda k: k.name)}
    return render_template('integration.html', **tpl_data)


@app.route('/job/<int:id_>')
def job(id_):
    session = app.db.session
    the_job = session.query(Job).get(id_)
    elapsed_history = the_job.get_elapsed_history(session)
    return render_template('job.html', job=the_job, history=elapsed_history)


# this is supposed to be called by sodd's to notify when a job_group is done
@app.route('/group_finished/<int:integration_id>')
def group_finished(integration_id):
    session = app.db.session
    integration = session.query(Integration).get(integration_id)

    # calcualte
    try:
        calculate_result(integration)
        calculate_diff(integration)
    except Integration.IntegrationException, exception:
        return str(exception)
    session.commit()

    # post integration
    get_diff(integration)

    # execute post-integration functions
    for setup in app.config['post-integration']:
        try:
            module_name, fun_name = setup.split(':')
            module = __import__(module_name)
            function = getattr(module, fun_name)
            function(integration)
        except Exception, e:
            print "Error executing post-integration %s" % setup
            print str(e)
            # TODO include traceback
            print

    return integration.result

