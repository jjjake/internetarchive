import responses

from internetarchive import get_session
from internetarchive.catalog import Catalog, CatalogTask
from tests.conftest import IaRequestsMock

TASKS_URL = 'https://catalogd.archive.org/services/tasks.php'


def _session():
    return get_session(config={'s3': {'access': 'access', 'secret': 'secret'}})


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
