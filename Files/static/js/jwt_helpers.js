/**
 * JWT helper utilities for CSRF token handling and authenticated requests.
 *
 * flask-jwt-extended stores the CSRF token in a cookie named
 * "csrf_access_token". Every mutating request (POST/PUT/PATCH/DELETE)
 * must send this value in the X-CSRF-TOKEN header.
 */

var _isRefreshing = false;
var _refreshQueue = [];

function getCsrfToken() {
    const match = document.cookie.match(/csrf_access_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

function getCsrfRefreshToken() {
    const match = document.cookie.match(/csrf_refresh_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

/**
 * Attempt to refresh the access token using the refresh token cookie.
 * Returns a promise that resolves to true on success, false on failure.
 */
function _refreshAccessToken() {
    if (_isRefreshing) {
        return new Promise(function (resolve) {
            _refreshQueue.push(resolve);
        });
    }

    _isRefreshing = true;

    return fetch('/api/v1/token/refresh', {
        method: 'POST',
        headers: { 'X-CSRF-TOKEN': getCsrfRefreshToken() }
    })
    .then(function (res) {
        _isRefreshing = false;
        var success = res.ok;
        _refreshQueue.forEach(function (cb) { cb(success); });
        _refreshQueue = [];
        return success;
    })
    .catch(function () {
        _isRefreshing = false;
        _refreshQueue.forEach(function (cb) { cb(false); });
        _refreshQueue = [];
        return false;
    });
}

/**
 * Wrapper around fetch that automatically includes the CSRF token header
 * for non-GET requests and silently refreshes expired access tokens.
 *
 * When a request receives a 401 response, authFetch will attempt to
 * refresh the access token via /api/v1/token/refresh and retry the
 * original request once. This works for all roles: student, admin,
 * and firm admin.
 */
function authFetch(url, options, _isRetry) {
    options = options || {};
    options.headers = options.headers || {};

    var method = (options.method || 'GET').toUpperCase();
    if (method !== 'GET' && method !== 'HEAD') {
        options.headers['X-CSRF-TOKEN'] = getCsrfToken();
    }

    return fetch(url, options).then(function (response) {
        // If we get a 401 and haven't retried yet, try refreshing the token
        if (response.status === 401 && !_isRetry) {
            return _refreshAccessToken().then(function (refreshed) {
                if (refreshed) {
                    // Update the CSRF token (it changes after refresh)
                    if (method !== 'GET' && method !== 'HEAD') {
                        options.headers['X-CSRF-TOKEN'] = getCsrfToken();
                    }
                    return authFetch(url, options, true);
                }
                // Refresh failed — return the original 401 response
                return response;
            });
        }
        return response;
    });
}

/**
 * Perform a JWT-aware logout via POST, then redirect to "/".
 * @param {string} logoutUrl - The logout endpoint, e.g. "/logout" or "/admin_logout"
 */
function jwtLogout(logoutUrl) {
    authFetch(logoutUrl, { method: 'POST' })
        .then(function () { window.location.href = '/'; })
        .catch(function () { window.location.href = '/'; });
}
