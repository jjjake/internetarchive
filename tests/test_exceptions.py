import internetarchive.exceptions


def test_AuthenticationError():
    try:
        raise internetarchive.exceptions.AuthenticationError('Authentication Failed')
    except Exception as exc:
        assert str(exc) == """Authentication Failed"""
