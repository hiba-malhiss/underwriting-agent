// Mirrors backend: documents/schemas.py (every kind of document)
export interface StoredDocument {
  name: string; // the blob's full name, e.g. "<applicant_id>/<random>-form.pdf"
  filename: string; // the name the user uploaded
  content_type: string;
  size: number; // bytes
  uploaded_at: string;
}

export interface DocumentListResponse {
  documents: StoredDocument[];
}

// Where a page's documents come from: how to list, upload and delete them
export interface DocumentSource {
  list: () => Promise<StoredDocument[]>;
  upload: (file: File) => Promise<StoredDocument>;
  remove: (name: string) => Promise<void>; // `name` = StoredDocument.name (the stored name)
}
