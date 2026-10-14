/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Point at a local backend during development, e.g. http://127.0.0.1:8000 */
  readonly VITE_API_BASE?: string;
  readonly VITE_SITE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
