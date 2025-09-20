# Make this module an alias for the Pyodide-native requests library
from pyodide_http import pyodide_requests as requests

# Expose the Session, exceptions, etc., so 'http.Session' still works in your agent code
Session = requests.Session
RequestException = requests.exceptions.RequestException
ConnectionError = requests.exceptions.ConnectionError
Timeout = requests.exceptions.Timeout
TooManyRedirects = requests.exceptions.TooManyRedirects
HTTPError = requests.exceptions.HTTPError