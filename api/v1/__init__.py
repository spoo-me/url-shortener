from flask import Blueprint


api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")


# Import endpoints to register their routes on api_v1
from . import shorten  # noqa: E402,F401
from . import keys  # noqa: E402,F401
from . import urls  # noqa: E402,F401
from . import management  # noqa: E402,F401
from . import stats  # noqa: E402,F401
from . import exports  # noqa: E402,F401
