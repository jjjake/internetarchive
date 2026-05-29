import json

import responses

import internetarchive.catalog as catalog_mod
from internetarchive import get_session
from internetarchive.catalog import Catalog, CatalogTask
from tests.conftest import IaRequestsMock

TASKS_URL = 'https://catalogd.archive.org/services/tasks.php'
# Status queries (get_tasks) go to session.host (archive.org), while task-log
# fetches are rewritten to catalogd.archive.org.
TASKS_STATUS_URL = 'https://archive.org/services/tasks.php'


def _session():
    return get_session(config={'s3': {'access': 'access', 'secret': 'secret'}})


def _patch_sleep(monkeypatch):
    monkeypatch.setattr(catalog_mod.time, 'sleep', lambda *a, **k: None)


def test_get_task_log():
    """``get_task_log`` fetches the log for a task_id and decodes the body."""
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL,
                 body='log line 1\nlog line 2\n',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        log = _session().get_task_log(123)
    assert log == 'log line 1\nlog line 2\n'


def test_get_task_log_with_params():
    """Extra ``params`` (e.g. ``lines``) are merged with ``task_log`` in the query string."""
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL,
                 body='last 10 lines',
                 match=[responses.matchers.query_param_matcher(
                     {'task_log': '123', 'lines': '10'})])
        log = _session().get_task_log(123, params={'lines': '10'})
    assert log == 'last 10 lines'


def test_get_task_log_request_kwargs_headers():
    """``request_kwargs`` headers (e.g. ``Range``) reach the outgoing request."""
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL,
                 body='partial content',
                 match=[
                     responses.matchers.query_param_matcher({'task_log': '123'}),
                     responses.matchers.header_matcher({'Range': 'bytes=-500'}),
                 ])
        log = _session().get_task_log(
            123, request_kwargs={'headers': {'Range': 'bytes=-500'}})
    assert log == 'partial content'


def test_catalogtask_task_log_passes_request_kwargs():
    """Regression: ``CatalogTask.task_log()`` must pass ``request_kwargs`` through to
    ``requests`` rather than into the ``params`` slot.

    If request_kwargs were passed positionally (the bug), the ``headers`` dict would be
    serialized as a query parameter and the ``Range`` header would never be sent, so
    both matchers below would fail.
    """
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL,
                 body='log',
                 match=[
                     responses.matchers.query_param_matcher({'task_log': '123'}),
                     responses.matchers.header_matcher({'Range': 'bytes=-10'}),
                 ])
        catalog = Catalog(_session(),
                          request_kwargs={'headers': {'Range': 'bytes=-10'}})
        task = CatalogTask({'task_id': 123}, catalog)
        log = task.task_log()
    assert log == 'log'


def test_request_task_log_returns_response():
    """``_request_task_log`` returns the raw Response (status + headers intact)."""
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL,
                 body='log body',
                 headers={'Last-Modified': 'Wed, 28 May 2026 00:00:00 GMT'},
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        r = CatalogTask._request_task_log(123, _session())
    assert r.status_code == 200
    assert r.headers['Last-Modified'] == 'Wed, 28 May 2026 00:00:00 GMT'
    assert r.content.decode('utf-8') == 'log body'


def test_select_log_lines():
    """``_select_log_lines`` replicates Tasks API ``lines`` semantics client-side."""
    text = 'a\nb\nc\nd\n'
    assert CatalogTask._select_log_lines(text, None) == 'a\nb\nc\nd\n'
    assert CatalogTask._select_log_lines(text, 2) == 'a\nb\n'
    assert CatalogTask._select_log_lines(text, -2) == 'c\nd\n'
    assert CatalogTask._select_log_lines(text, 0) == ''
    assert CatalogTask._select_log_lines(text, 100) == 'a\nb\nc\nd\n'
    assert CatalogTask._select_log_lines('', -5) == ''


def _task_status_body(status, category='catalog', task_id=123):
    """Build a one-task Tasks API response body with the given status."""
    return json.dumps({'task_id': task_id, 'identifier': 'foo',
                       'category': category, 'status': status,
                       'submittime': '2026-05-28 12:00:00'}) + '\n'


def _assert_task_active(status_body, expected):
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_STATUS_URL, body=status_body,
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '123'}, strict_match=False)])
        assert CatalogTask._task_is_active(123, _session()) is expected


def test_task_is_active():
    """``_task_is_active`` keys off the task's ``status``, not catalog membership.

    A running/queued task is active; an errored or done task is finished even
    though it may still be returned by the query (errored tasks linger in the
    catalog awaiting admin).
    """
    _assert_task_active(_task_status_body('running'), True)
    _assert_task_active(_task_status_body('queued'), True)
    # Regression: an errored task is terminal (previously hung forever).
    _assert_task_active(_task_status_body('error'), False)
    # A done task is returned from history with status null -> terminal.
    _assert_task_active(_task_status_body(None, category='history'), False)
    # Task not found at all -> terminal.
    _assert_task_active('', False)


def test_follow_task_log_yields_delta(monkeypatch):
    """Successive fetches yield only newly appended content; auto-stops."""
    _patch_sleep(monkeypatch)
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL, body='l1\n',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        rsps.add(responses.GET, TASKS_URL, body='l1\nl2\n',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        rsps.add(responses.GET, TASKS_STATUS_URL, body='',
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '123'}, strict_match=False)])
        chunks = list(CatalogTask.follow_task_log(123, _session()))
    assert chunks == ['l1\n', 'l2\n']


def test_follow_task_log_seeds_lines(monkeypatch):
    """``lines`` seeds only the trailing backlog before following."""
    _patch_sleep(monkeypatch)
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL, body='a\nb\nc\nd\n',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        rsps.add(responses.GET, TASKS_STATUS_URL, body='',
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '123'}, strict_match=False)])
        chunks = list(CatalogTask.follow_task_log(123, _session(), lines=-2))
    assert chunks == ['c\nd\n']


def test_follow_task_log_304_yields_nothing(monkeypatch):
    """A 304 response adds no output."""
    _patch_sleep(monkeypatch)
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL, body='x\n',
                 headers={'Last-Modified': 'Wed, 28 May 2026 00:00:00 GMT'},
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        rsps.add(responses.GET, TASKS_URL, status=304,
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        rsps.add(responses.GET, TASKS_URL, body='x\n',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        rsps.add(responses.GET, TASKS_STATUS_URL, body='',
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '123'}, strict_match=False)])
        chunks = list(CatalogTask.follow_task_log(123, _session()))
    assert chunks == ['x\n']


def test_follow_task_log_resets_on_truncation(monkeypatch):
    """If the log shrinks (rotation), re-emit the new shorter body."""
    _patch_sleep(monkeypatch)
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL, body='aaa\n',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        rsps.add(responses.GET, TASKS_URL, body='x\n',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        rsps.add(responses.GET, TASKS_STATUS_URL, body='',
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '123'}, strict_match=False)])
        chunks = list(CatalogTask.follow_task_log(123, _session()))
    assert chunks == ['aaa\n', 'x\n']


def test_session_follow_task_log(monkeypatch):
    """``ArchiveSession.follow_task_log`` delegates to CatalogTask.follow_task_log."""
    _patch_sleep(monkeypatch)
    with IaRequestsMock() as rsps:
        rsps.add(responses.GET, TASKS_URL, body='only line\n',
                 match=[responses.matchers.query_param_matcher({'task_log': '123'})])
        rsps.add(responses.GET, TASKS_STATUS_URL, body='',
                 match=[responses.matchers.query_param_matcher(
                     {'task_id': '123'}, strict_match=False)])
        chunks = list(_session().follow_task_log(123))
    assert chunks == ['only line\n']
