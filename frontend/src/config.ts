// Upload rules. Mirrors backend: storage/validation.py (…_TYPES), settings.py → max_upload_mb
export const APPLICANT_FILE_TYPES = [".pdf", ".png", ".jpg", ".jpeg"];
export const REQUIREMENT_FILE_TYPES = [".pdf", ".docx", ".txt", ".md"];
export const MAX_UPLOAD_MB = 20;

// The applicant the app works on, from .env (until applicants are stored)
export const APPLICANT_ID: string = import.meta.env.VITE_APPLICANT_ID;
