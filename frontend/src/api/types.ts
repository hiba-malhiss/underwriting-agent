export interface ApplicationDocument {
  name: string; // the blob's full name: "<application_id>/<random>-form.pdf"
  filename: string; // the name the user uploaded
  content_type: string;
  size: number; // bytes
  uploaded_at: string;
}

export interface DocumentListResponse {
  documents: ApplicationDocument[];
}
