import json

import responses

import internetarchive.catalog as catalog_mod
from tests.conftest import IaRequestsMock, ia_call

TASKS_URL = 'https://catalogd.archive.org/services/tasks.php'
# Status queries (get_tasks) go to session.host (archive.org).
TASKS_STATUS_URL = 'https://archive.org/services/tasks.php'


def _task_status_body(status, category='catalog', task_id=123):
    """Build a one-task Tasks API response body with the given status."""
    return json.dumps({'task_id': task_id, 'identifier': 'foo',
                       'category': category, 'status': status,
                       'submittime': '2026-05-28 12:00:00'}) + '\n'


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


def test_ia_tasks_follow_task_log(capsys, monkeypatch):
    """``ia tasks -F <id>`` streams the log and stops when the task finishes."""
    monkeypatch.setattr(catalog_mod.time, 'sleep', lambda *a, **k: None)
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL, body='streamed line\n',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        # Task exists (returned from history, done) -> upfront check passes and
        # the loop terminates after emitting the log.
        rsps.add(responses.GET, TASKS_STATUS_URL,
                 body=_task_status_body(None, category='history'),
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '123'}, strict_match=False)])
        ia_call(['ia', 'tasks', '-F', '123'])
    out, _err = capsys.readouterr()
    assert 'streamed line' in out


def test_ia_tasks_follow_task_log_lines(capsys, monkeypatch):
    """``-p lines=-2`` seeds only the trailing backlog before following."""
    monkeypatch.setattr(catalog_mod.time, 'sleep', lambda *a, **k: None)
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL, body='a\nb\nc\nd\n',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        rsps.add(responses.GET, TASKS_STATUS_URL,
                 body=_task_status_body(None, category='history'),
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '123'}, strict_match=False)])
        ia_call(['ia', 'tasks', '-F', '123', '-p', 'lines=-2'])
    out, _err = capsys.readouterr()
    assert 'c\nd' in out
    assert 'a\nb' not in out


def test_ia_tasks_follow_task_log_not_found(capsys, monkeypatch):
    """An unknown task id fails fast with a clear error and exit 1."""
    monkeypatch.setattr(catalog_mod.time, 'sleep', lambda *a, **k: None)
    with IaRequestsMock() as rsps:
        # Unknown id -> Tasks API returns an empty body (no matching task).
        rsps.add(responses.GET, TASKS_STATUS_URL, body='',
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '999'}, strict_match=False)])
        ia_call(['ia', 'tasks', '-F', '999'], expected_exit_code=1)
    _out, err = capsys.readouterr()
    assert 'task 999 not found' in err


def test_ia_tasks_get_and_follow_mutually_exclusive():
    """``-G`` and ``-F`` cannot be combined (argparse error -> exit 2)."""
    ia_call(['ia', 'tasks', '-G', '123', '-F', '123'], expected_exit_code=2)
