from internetarchive.api import get_item
from tests.conftest import IaRequestsMock


def test_bad_mediatype():
    # this identifier actually has this malformed data
    ident = 'CIA-RDP96-00789R000700210007-5'
    body = '{"metadata": {"mediatype":["texts","texts"]}}'
    with IaRequestsMock() as rsps:
        rsps.add_metadata_mock(ident, body=body)
        # should complete without error
        get_item(ident)
