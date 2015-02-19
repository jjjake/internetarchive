# Mine class
# ________________________________________________________________________________________
class Mine(object):
    """internetarchive.mine.Mine() has been deprecated"""
    # __init__()
    # ____________________________________________________________________________________
    def __init__(self, *args, **kwargs):
        raise DeprecationWarning((
            'internetarchive.mine has been deprecated. '
            'Please use the iamine module: https://github.com/jjjake/iamine '))
