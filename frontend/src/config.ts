// Document uploads. Mirrors backend: validation.py → ALLOWED_TYPES, settings.py → max_upload_mb
export const DOCUMENT_FILE_TYPES = [".pdf", ".png", ".jpg", ".jpeg"];
export const MAX_UPLOAD_MB = 20;

// The application the app works on, from .env (until applications are stored)
export const APPLICATION_ID: string = import.meta.env.VITE_APPLICATION_ID;
