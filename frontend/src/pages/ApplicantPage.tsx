import { useDeleteDocument, useDocumentsQuery, useUploadDocument } from "@/api/documents";
import { DocumentList } from "@/components/documents/DocumentList/DocumentList";
import { DocumentUpload } from "@/components/documents/DocumentUpload/DocumentUpload";
import { APPLICANT_FILE_TYPES, APPLICANT_ID } from "@/config";

export function ApplicantPage() {
  const documents = useDocumentsQuery("applicant", APPLICANT_ID);
  const upload = useUploadDocument("applicant", APPLICANT_ID);
  const remove = useDeleteDocument("applicant", APPLICANT_ID);

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
        uploading={upload.isPending}
        onUpload={upload.mutateAsync}
      />
      <DocumentList
        documents={documents.data ?? []}
        loading={documents.isPending}
        error={documents.error?.message ?? null}
        deleting={remove.isPending ? remove.variables : null}
        onDelete={remove.mutateAsync}
      />
    </div>
  );
}
