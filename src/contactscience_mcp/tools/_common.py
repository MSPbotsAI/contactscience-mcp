from .._json import error_envelope

NO_TOKEN = error_envelope(
    "not_configured",
    "No Contact Science credentials. Send the X-ContactScience-Authorization header.",
    False,
)
