import { useCallback, useEffect, useState } from "react";
import type { DocumentSource, StoredDocument } from "../api/types";

// A page's documents: loaded when the page opens, refreshed after an upload.
// `source` must be stable (a module constant or memoised), or this reloads every render.
export function useDocuments(source: DocumentSource) {
  const [documents, setDocuments] = useState<StoredDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setDocuments(await source.list());
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [source]);

  useEffect(() => {
    setLoading(true);
    void refresh();
  }, [refresh]);

  // Throws so the caller can show the reason (wrong type, too large, storage down)
  const upload = useCallback(
    async (file: File) => {
      setUploading(true);
      try {
        const document = await source.upload(file);
        await refresh();
        return document;
      } finally {
        setUploading(false);
      }
    },
    [source, refresh],
  );

  return { documents, loading, uploading, error, upload, refresh };
}
