import { useDeleteDocument, useDocumentsQuery, useUploadDocument } from "@/api/documents";
import { DocumentList } from "@/components/documents/DocumentList/DocumentList";
import { DocumentUpload } from "@/components/documents/DocumentUpload/DocumentUpload";
import { REQUIREMENT_FILE_TYPES } from "@/config";

// The underwriting guidelines the eligibility check is based on
export function RequirementsPage() {
  const documents = useDocumentsQuery("requirement");
  const upload = useUploadDocument("requirement");
  const remove = useDeleteDocument("requirement");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Requirements</h1>
        <p className="text-sm text-muted-foreground">
          Underwriting guidelines. Uploading a file with the same name replaces the old version.
        </p>
      </div>
      <DocumentUpload
        title="Upload guidelines"
        description="Eligibility rules, required documents, medical criteria."
        fileTypes={REQUIREMENT_FILE_TYPES}
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
