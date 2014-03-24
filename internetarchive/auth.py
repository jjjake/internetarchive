import requests.auth


class S3Auth(requests.auth.AuthBase):
    """Attaches S3 Basic Authentication to the given Request object."""
    def __init__(self, access_key=None, secret_key=None):
        self.access_key = access_key
        self.secret_key = secret_key

    def __call__(self, r):
        auth_str = 'LOW {a}:{s}'.format(a=self.access_key, s=self.secret_key)
        r.headers['Authorization'] = auth_str
        return r
