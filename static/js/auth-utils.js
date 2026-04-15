/**
 * Shared auth utilities for dashboard pages.
 * Requires window.g.jwt_claims to be set by the template before this loads.
 */

async function authFetch(url, options = {}) {
    const defaultOptions = {
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    };
    const response = await fetch(url, { ...defaultOptions, ...options });
    if (response.status === 401) {
        window.location.href = '/';
    }
    return response;
}

async function logout() {
    const res = await authFetch('/auth/logout', { method: 'POST' });
    if (res.ok) {
        window.location.href = '/';
    }
}
