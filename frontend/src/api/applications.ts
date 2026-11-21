import { request } from "./http";
import type { ApplicationDocument, DocumentListResponse } from "./types";

export async function listDocuments(applicationId: string): Promise<ApplicationDocument[]> {
  const { documents } = await request<DocumentListResponse>(
    `/applications/${applicationId}/documents`,
  );
  return documents;
}

export function uploadDocument(applicationId: string, file: File): Promise<ApplicationDocument> {
  const body = new FormData();
  body.append("file", file); // the backend's `file: UploadFile` parameter
  return request<ApplicationDocument>(`/applications/${applicationId}/documents`, {
    method: "POST",
    body,
  });
}
