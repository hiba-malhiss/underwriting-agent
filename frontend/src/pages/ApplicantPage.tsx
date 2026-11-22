import { applicantDocuments } from "@/api/documents";
import { DocumentList } from "@/components/documents/DocumentList/DocumentList";
import { DocumentUpload } from "@/components/documents/DocumentUpload/DocumentUpload";
import { APPLICANT_FILE_TYPES, APPLICANT_ID } from "@/config";
import { useDocuments } from "@/hooks/useDocuments";

// Created once, so the hook doesn't reload on every render
const source = applicantDocuments(APPLICANT_ID);

export function ApplicantPage() {
  const { documents, loading, uploading, error, upload } = useDocuments(source);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Applicant</h1>
        <p className="font-mono text-sm text-muted-foreground">{APPLICANT_ID}</p>
      </div>
      <DocumentUpload
        title="Upload documents"
        description="Signed insurance form, medical reports, Emirates ID."
        fileTypes={APPLICANT_FILE_TYPES}
        uploading={uploading}
        onUpload={upload}
      />
      <DocumentList documents={documents} loading={loading} error={error} />
    </div>
  );
}
