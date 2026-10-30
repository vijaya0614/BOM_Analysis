/** Same-origin API base; Vite and Nginx proxy backend paths to the unified API. */
export const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '');
export const SENTINEL_API_BASE = API_BASE;
export const SUBSTITUTE_API_BASE = API_BASE;
