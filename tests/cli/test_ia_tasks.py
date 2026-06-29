import json

import requests
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
    """``ia tasks -f <id>`` streams the log and stops when the task finishes."""
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
        ia_call(['ia', 'tasks', '-f', '123'])
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
        ia_call(['ia', 'tasks', '-f', '123', '-p', 'lines=-2'])
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
        ia_call(['ia', 'tasks', '-f', '999'], expected_exit_code=1)
    _out, err = capsys.readouterr()
    assert 'task 999 not found' in err


def test_ia_tasks_follow_task_log_positive_lines_rejected(capsys):
    """A positive ``-p lines=N`` (head of the log) fails fast (exit 1).

    Keeps Tasks API semantics consistent with ``-G``; the head can't be
    followed. No network request is made.
    """
    ia_call(['ia', 'tasks', '-f', '123', '-p', 'lines=2'], expected_exit_code=1)
    _out, err = capsys.readouterr()
    assert "'lines' must be negative" in err


def test_ia_tasks_follow_task_log_forwards_params(capsys, monkeypatch):
    """Non-``lines`` ``-p`` params are forwarded to the task-log request."""
    monkeypatch.setattr(catalog_mod.time, 'sleep', lambda *a, **k: None)
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL, body='streamed line\n',
                 match=[responses.matchers.query_param_matcher(
                     {'task_log': '123', 'foo': 'bar'})])
        rsps.add(responses.GET, TASKS_STATUS_URL,
                 body=_task_status_body(None, category='history'),
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '123'}, strict_match=False)])
        ia_call(['ia', 'tasks', '-f', '123', '-p', 'foo=bar'])
    out, _err = capsys.readouterr()
    assert 'streamed line' in out


def test_ia_tasks_get_and_follow_mutually_exclusive():
    """``-G`` and ``-f`` cannot be combined (argparse error -> exit 2)."""
    ia_call(['ia', 'tasks', '-G', '123', '-f', '123'], expected_exit_code=2)


def test_ia_tasks_identifier_and_follow_rejected():
    """A positional identifier plus ``-f`` is rejected (exit 2), not ignored."""
    ia_call(['ia', 'tasks', 'foo', '-f', '123'], expected_exit_code=2)


def test_ia_tasks_identifier_and_get_log_rejected():
    """A positional identifier plus ``-G`` is rejected (exit 2), not ignored."""
    ia_call(['ia', 'tasks', 'foo', '-G', '123'], expected_exit_code=2)


def test_ia_tasks_follow_task_log_request_error(capsys, monkeypatch):
    """Persistent request failures print a clean one-line error and exit 1."""
    monkeypatch.setattr(catalog_mod.time, 'sleep', lambda *a, **k: None)
    with IaRequestsMock() as rsps:
        # Upfront existence check succeeds: the task is running.
        rsps.add(responses.GET, TASKS_STATUS_URL,
                 body=_task_status_body('running'),
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '123'}, strict_match=False)])
        for _ in range(catalog_mod.FOLLOW_MAX_CONSECUTIVE_ERRORS):
            rsps.add(responses.GET, TASKS_URL,
                     body=requests.exceptions.ConnectionError('connection reset'),
                     match=[responses.matchers.query_param_matcher(
                         {'task_log': '123'})])
        ia_call(['ia', 'tasks', '-f', '123'], expected_exit_code=1)
    _out, err = capsys.readouterr()
    assert 'error: connection reset' in err
    assert 'Traceback' not in err
