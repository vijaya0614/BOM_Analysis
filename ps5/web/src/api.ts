/**
 * One server-side API origin for local development and deployed builds.
 * Provider credentials remain on the Python server; this value is safe to
 * expose because it is only an endpoint address.
 */
export const SENTINEL_API_BASE = (
  import.meta.env.VITE_SENTINEL_API_BASE || 'http://127.0.0.1:8001'
).replace(/\/$/, '');

/** Raw substitute/evidence API; it intentionally remains separate from risk_api. */
export const SUBSTITUTE_API_BASE = (
  import.meta.env.VITE_SUBSTITUTE_API_BASE || 'http://127.0.0.1:8000'
).replace(/\/$/, '');
