import { DocumentList } from "@/components/documents/DocumentList/DocumentList";
import { DocumentUpload } from "@/components/documents/DocumentUpload/DocumentUpload";
import { APPLICATION_ID } from "@/config";
import { useApplicationDocuments } from "@/hooks/useApplicationDocuments";

export function ApplicationPage() {
  const { documents, loading, uploading, error, upload } = useApplicationDocuments(APPLICATION_ID);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Application</h1>
        <p className="font-mono text-sm text-muted-foreground">{APPLICATION_ID}</p>
      </div>
      <DocumentUpload uploading={uploading} onUpload={upload} />
      <DocumentList documents={documents} loading={loading} error={error} />
    </div>
  );
}
