import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { http } from "./http";
import type { DocumentListResponse, StoredDocument } from "./types";

// Mirrors backend: documents/types.py → DocumentType
export type DocumentType = "applicant" | "requirement";

// GET/POST/DELETE /documents?type=…[&applicant_id=…]: one endpoint for every kind of document.
// applicant_id is only sent for applicant documents (the backend refuses it for the others).
function params(type: DocumentType, applicantId?: string) {
  return { type, ...(applicantId ? { applicant_id: applicantId } : {}) };
}

export async function listDocuments(type: DocumentType, applicantId?: string) {
  const response = await http.get<DocumentListResponse>("/documents", {
    params: params(type, applicantId),
  });
  return response.data.documents;
}

// Guidelines (requirement): uploading a file with the same name replaces it
export async function uploadDocument(type: DocumentType, file: File, applicantId?: string) {
  const body = new FormData();
  body.append("file", file); // the backend's `file: UploadFile` parameter
  const response = await http.post<StoredDocument>("/documents", body, {
    params: params(type, applicantId),
  });
  return response.data;
}

// GET /documents/file: a URL, not a request, so a viewer (e.g. the PDF drawer) can load it itself
export function documentFileUrl(type: DocumentType, name: string, applicantId?: string) {
  return `/documents/file?${new URLSearchParams({ ...params(type, applicantId), name })}`;
}

// `name` = StoredDocument.name (the stored name, from the list)
export async function deleteDocument(type: DocumentType, name: string, applicantId?: string) {
  await http.delete("/documents", { params: { ...params(type, applicantId), name } });
}


export const documentsKey = (type: DocumentType, applicantId?: string) =>
  ["documents", type, applicantId ?? null] as const;

export function useDocumentsQuery(type: DocumentType, applicantId?: string) {
  return useQuery({
    queryKey: documentsKey(type, applicantId),
    queryFn: () => listDocuments(type, applicantId),
  });
}

// mutateAsync rejects on failure (so the caller can show the reason) and resolves after the
// list has reloaded (onSuccess returns the invalidation)
export function useUploadDocument(type: DocumentType, applicantId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadDocument(type, file, applicantId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentsKey(type, applicantId) }),
  });
}

export function useDeleteDocument(type: DocumentType, applicantId?: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => deleteDocument(type, name, applicantId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: documentsKey(type, applicantId) }),
  });
}
