import { useCallback, useEffect, useState } from "react";
import { listDocuments, uploadDocument } from "../api/applications";
import type { ApplicationDocument } from "../api/types";

// An application's documents: loaded when the application opens, refreshed after an upload
export function useApplicationDocuments(applicationId: string) {
  const [documents, setDocuments] = useState<ApplicationDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setDocuments(await listDocuments(applicationId));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    setLoading(true);
    void refresh();
  }, [refresh]);

  // Throws so the caller can show the reason (wrong type, too large, storage down)
  const upload = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        const document = await uploadDocument(applicationId, file);
        await refresh();
        return document;
      } finally {
        setUploading(false);
      }
    },
    [applicationId, refresh],
  );

  return { documents, loading, uploading, error, upload, refresh };
}
