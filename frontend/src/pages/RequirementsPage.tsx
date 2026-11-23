import { requirementDocuments } from "@/api/documents";
import { DocumentList } from "@/components/documents/DocumentList/DocumentList";
import { DocumentUpload } from "@/components/documents/DocumentUpload/DocumentUpload";
import { REQUIREMENT_FILE_TYPES } from "@/config";
import { useDocuments } from "@/hooks/useDocuments";

// The underwriting guidelines the eligibility check is based on
export function RequirementsPage() {
  const { documents, loading, uploading, deleting, error, upload, remove } = useDocuments(requirementDocuments);

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
        uploading={uploading}
        onUpload={upload}
      />
      <DocumentList
        documents={documents}
        loading={loading}
        error={error}
        deleting={deleting}
        onDelete={remove}
      />
    </div>
  );
}
