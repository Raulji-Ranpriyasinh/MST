/**
 * JWT helper utilities for CSRF token handling and authenticated requests.
 *
 * flask-jwt-extended stores the CSRF token in a cookie named
 * "csrf_access_token". Every mutating request (POST/PUT/PATCH/DELETE)
 * must send this value in the X-CSRF-TOKEN header.
 */

function getCsrfToken() {
    const match = document.cookie.match(/csrf_access_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
}

/**
 * Wrapper around fetch that automatically includes the CSRF token header
 * for non-GET requests.  Usage is identical to the native fetch() API.
 */
function authFetch(url, options) {
    options = options || {};
    options.headers = options.headers || {};

    const method = (options.method || 'GET').toUpperCase();
    if (method !== 'GET' && method !== 'HEAD') {
        options.headers['X-CSRF-TOKEN'] = getCsrfToken();
    }

    return fetch(url, options);
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
