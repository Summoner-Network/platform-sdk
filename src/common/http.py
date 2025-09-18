import http.client
import urllib.parse
import ssl
import json
import gzip
import zlib
import socket

# --- Exceptions ---

class RequestException(IOError):
    """Base exception class for simple_requests."""
    pass

class ConnectionError(RequestException):
    """A connection error occurred."""
    pass

class Timeout(RequestException):
    """The request timed out."""
    pass

class TooManyRedirects(RequestException):
    """Too many redirects."""
    pass

class HTTPError(RequestException):
    """An HTTP error occurred."""
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response

# --- Response Object ---

class Response:
    """Encapsulates the HTTP response."""
    def __init__(self, status, reason, headers, content, url, history=None):
        self.status_code = status
        self.reason = reason
        # Headers are stored with lowercase keys for case-insensitive access.
        self.headers = headers
        self._content = content
        self.url = url # Final URL after redirects
        self.history = history or []
        self.encoding = self._get_encoding()

    def _get_encoding(self):
        """Determine the encoding from the Content-Type header."""
        content_type = self.headers.get('content-type', '')
        if 'charset=' in content_type:
            try:
                encoding = content_type.split('charset=')[-1].strip().strip('"\'')
                # Validate encoding
                import codecs
                try:
                    codecs.lookup(encoding)
                    return encoding
                except LookupError:
                    pass
            except IndexError:
                pass
        # Default to UTF-8 for modern web practices.
        return 'utf-8'

    @property
    def content(self):
        """Returns the content of the response, in bytes (already decompressed)."""
        return self._content

    @property
    def text(self):
        """Returns the content of the response, in unicode."""
        try:
            return self._content.decode(self.encoding)
        except UnicodeDecodeError:
            # Fallback if the detected encoding fails (e.g., server misconfiguration)
            return self._content.decode('latin-1')

    def json(self, **kwargs):
        """Parses the response body as JSON."""
        try:
            return json.loads(self.text, **kwargs)
        except json.JSONDecodeError as e:
            raise RequestException(f"Failed to decode JSON response: {e}")

    def raise_for_status(self):
        """Raises HTTPError for 4xx or 5xx responses."""
        if 400 <= self.status_code < 600:
            message = f"{self.status_code} {self.reason} for url: {self.url}"
            raise HTTPError(message, response=self)

    def __repr__(self):
        return f"<Response [{self.status_code}]>"

# --- Core Logic (Session-like structure) ---

class SimpleRequestsSession:
    """A simple requests-alike session implementation."""

    def __init__(self, allow_redirects=True, max_redirects=10, timeout=30, verify=True):
        self.allow_redirects = allow_redirects
        self.max_redirects = max_redirects
        self.timeout = timeout
        self.verify = verify
        self.ssl_context = self._create_ssl_context(verify)

    def _create_ssl_context(self, verify):
        """Creates an SSL context based on the verification setting."""
        try:
            context = ssl.create_default_context()
        except Exception:
            # Fallback for environments where create_default_context fails or is missing
            context = ssl.SSLContext(ssl.PROTOCOL_TLS)
            context.verify_mode = ssl.CERT_REQUIRED
            context.check_hostname = True

        if not verify:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context

    def _decode_content(self, content, encoding):
        """Decode compressed content."""
        if not encoding:
            return content
            
        encoding = encoding.lower()

        if encoding == 'gzip':
            try:
                return gzip.decompress(content)
            except (OSError, IOError) as e:
                raise RequestException(f"Failed to decode gzip content: {e}")
        elif encoding == 'deflate':
            try:
                # Try standard deflate (zlib wrapper)
                return zlib.decompress(content)
            except zlib.error:
                try:
                    # Try raw deflate (used by some servers)
                    # -zlib.MAX_WBITS enables raw deflate decoding
                    return zlib.decompress(content, -zlib.MAX_WBITS)
                except zlib.error as e:
                    raise RequestException(f"Failed to decode deflate content: {e}")
        # If encoding is unknown (e.g., 'br' Brotli), return as is.
        return content

    def _prepare_headers(self, user_headers):
        """Merges default headers with user-provided headers."""
        headers = {
            'User-Agent': 'python-simple-requests/1.1',
            'Accept-Encoding': 'gzip, deflate',
            'Accept': '*/*'
        }
        if user_headers:
            # Case-insensitive merge
            header_keys_lower = {k.lower(): k for k in headers}
            for k, v in user_headers.items():
                lower_k = k.lower()
                if lower_k in header_keys_lower:
                    del headers[header_keys_lower[lower_k]]
                headers[k] = v
        return headers

    def _prepare_body(self, data, json_data, headers):
        """Encodes the body and updates headers (Content-Type)."""
        body = None
        
        # Helper to check if Content-Type is set (case-insensitive)
        content_type_set = any(key.lower() == 'content-type' for key in headers)

        if data is not None and json_data is not None:
             raise ValueError("Cannot provide both 'data' and 'json' arguments.")

        if json_data is not None:
            body = json.dumps(json_data).encode('utf-8')
            if not content_type_set:
                headers['Content-Type'] = 'application/json'
        
        elif data is not None:
            if isinstance(data, (dict, list)):
                # Default to form encoding
                body = urllib.parse.urlencode(data, doseq=True).encode('utf-8')
                if not content_type_set:
                    headers['Content-Type'] = 'application/x-www-form-urlencoded'
            elif isinstance(data, str):
                body = data.encode('utf-8')
            elif isinstance(data, bytes):
                body = data
            elif hasattr(data, 'read'):
                # File-like object. Read into memory for simplicity.
                body = data.read()
                if not isinstance(body, bytes):
                     raise TypeError("File-like object must return bytes when read.")
            else:
                body = str(data).encode('utf-8')
                
        # http.client automatically adds Content-Length if the body is bytes/str.
        return body

    def _url_with_params(self, url, params):
        """Helper to correctly append parameters to a URL."""
        if not params:
            return url
            
        parsed = urllib.parse.urlparse(url)
        query = parsed.query
        # doseq=True handles lists as multiple values for the same key
        encoded_params = urllib.parse.urlencode(params, doseq=True)
        
        if query:
            query = f"{query}&{encoded_params}"
        else:
            query = encoded_params
        
        # Reconstruct the URL
        return urllib.parse.urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment)
        )

    def _remove_body_headers(self, headers):
        """Removes Content-Type and Content-Length headers (case-insensitive)."""
        keys_to_remove = []
        for key in headers.keys():
            lower_key = key.lower()
            if lower_key == 'content-length' or lower_key == 'content-type':
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del headers[key]
        return headers


    def request(self, method, url, params=None, data=None, json=None, headers=None, **kwargs):
        """
        Constructs and sends an HTTP request. Handles redirects automatically.
        """
        
        # 1. Initialize settings
        allow_redirects = kwargs.get('allow_redirects', self.allow_redirects)
        max_redirects = kwargs.get('max_redirects', self.max_redirects)
        timeout = kwargs.get('timeout', self.timeout)
        
        # Initialize state for the request loop
        current_url = self._url_with_params(url, params)
        current_method = method.upper()
        request_headers = self._prepare_headers(headers)
        
        # Track original data/json for potential 307/308 redirects
        current_data = data
        current_json = json
        
        redirect_count = 0
        history = []

        # 2. Main request loop
        while True:
            if redirect_count > max_redirects:
                raise TooManyRedirects(f"Exceeded {max_redirects} redirects.")

            # Prepare body for this iteration
            # Use a copy of headers as _prepare_body might modify them (e.g., add Content-Type)
            iteration_headers = request_headers.copy()
            try:
                body = self._prepare_body(current_data, current_json, iteration_headers)
            except Exception as e:
                raise RequestException(f"Error preparing request body: {e}")

            # Parse the URL
            parsed_url = urllib.parse.urlparse(current_url)
            scheme = parsed_url.scheme
            host = parsed_url.hostname
            port = parsed_url.port
            path = parsed_url.path or '/'
            if parsed_url.query:
                path += '?' + parsed_url.query

            if not host:
                raise ValueError(f"Invalid URL: {current_url}")

            # Establish connection
            conn = None
            try:
                if scheme == 'https':
                    conn = http.client.HTTPSConnection(host, port or 443, context=self.ssl_context, timeout=timeout)
                elif scheme == 'http':
                    conn = http.client.HTTPConnection(host, port or 80, timeout=timeout)
                else:
                    raise ValueError(f"Unsupported scheme: {scheme}")

                # Send the request
                conn.request(current_method, path, body=body, headers=iteration_headers)

                # Get the response
                resp = conn.getresponse()

                # Read content immediately
                raw_content = resp.read()
                response_headers = {k.lower(): v for k, v in resp.getheaders()}
                
                # Decode content
                try:
                    decoded_content = self._decode_content(raw_content, response_headers.get('content-encoding'))
                except RequestException:
                    # If decompression fails, use the raw content
                    decoded_content = raw_content

                # Create a preliminary response object
                temp_response = Response(resp.status, resp.reason, response_headers, decoded_content, current_url)

                # Check for redirects (301, 302, 303, 307, 308)
                if allow_redirects and resp.status in (301, 302, 303, 307, 308):
                    location = resp.getheader('Location')
                    if location:
                        history.append(temp_response)
                        # Handle relative redirects
                        current_url = urllib.parse.urljoin(current_url, location)
                        redirect_count += 1

                        # HTTP specification behavior for redirects:
                        # 301, 302, 303: Generally switch to GET (or HEAD) and drop body.
                        # 307, 308: Retain original method and body.
                        
                        if resp.status in (301, 302, 303):
                             if current_method != 'HEAD':
                                current_method = 'GET'
                             
                             # Drop the body and related headers
                             current_data = None
                             current_json = None
                             self._remove_body_headers(request_headers)

                        # Close the current connection before retrying
                        conn.close()
                        continue # Follow the redirect

                # If not redirecting, this is the final response
                temp_response.history = history
                return temp_response

            except socket.timeout:
                raise Timeout(f"The request timed out after {timeout} seconds.")
            except socket.gaierror as e:
                 raise ConnectionError(f"DNS resolution failed for host {host}: {e}")
            except (http.client.HTTPException, socket.error, ssl.SSLError) as e:
                raise ConnectionError(f"Connection error: {e}")
            except Exception as e:
                 raise RequestException(f"An unexpected error occurred: {e}")
            finally:
                if conn:
                    conn.close()

    # Define helper methods for common HTTP verbs
    def get(self, url, params=None, **kwargs):
        return self.request("GET", url, params=params, **kwargs)

    def post(self, url, data=None, json=None, **kwargs):
        return self.request("POST", url, data=data, json=json, **kwargs)

    def put(self, url, data=None, **kwargs):
        return self.request("PUT", url, data=data, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def head(self, url, **kwargs):
        return self.request("HEAD", url, **kwargs)

    def options(self, url, **kwargs):
        return self.request("OPTIONS", url, **kwargs)

# --- Public API (Top-level functions) ---

# Create a default session instance for top-level functions
_default_session = SimpleRequestsSession()

def request(method, url, **kwargs):
    return _default_session.request(method, url, **kwargs)

def get(url, params=None, **kwargs):
    return _default_session.get(url, params=params, **kwargs)

def post(url, data=None, json=None, **kwargs):
    return _default_session.post(url, data=data, json=json, **kwargs)

def put(url, data=None, **kwargs):
    return _default_session.put(url, data=data, **kwargs)

def delete(url, **kwargs):
    return _default_session.delete(url, **kwargs)

def head(url, **kwargs):
    return _default_session.head(url, **kwargs)

def options(url, **kwargs):
    return _default_session.options(url, **kwargs)

# Alias the Session class
Session = SimpleRequestsSession