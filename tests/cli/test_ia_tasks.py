import responses

from tests.conftest import IaRequestsMock, ia_call

TASKS_URL = 'https://catalogd.archive.org/services/tasks.php'


def test_ia_tasks_get_task_log(capsys):
    """``ia tasks -G <task_id>`` prints the task log."""
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL,
                 body='the task log',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        ia_call(['ia', 'tasks', '-G', '123'])
    out, _err = capsys.readouterr()
    assert 'the task log' in out


def test_ia_tasks_get_task_log_with_params(capsys):
    """Regression (#764): ``-p`` params must not crash when combined with ``-G``.

    The params are merged into the task log request's query string.
    """
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL,
                 body='last 10 lines',
                 match=[responses.matchers.query_param_matcher(
                     {'task_log': '123', 'lines': '10'})])
        ia_call(['ia', 'tasks', '-G', '123', '-p', 'lines=10'])
    out, _err = capsys.readouterr()
    assert 'last 10 lines' in out
