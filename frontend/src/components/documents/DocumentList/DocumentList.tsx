import type { ReactNode } from "react";
import { FileTextIcon, ImageIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";
import type { StoredDocument } from "@/api/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface Props {
  documents: StoredDocument[];
  loading: boolean;
  error: string | null;
  deleting: string | null; // the stored name being deleted, if any
  onDelete: (name: string) => Promise<unknown>;
  // Extra buttons per row (e.g. "Suggest rules" for guidelines), shown before delete
  renderActions?: (document: StoredDocument) => ReactNode;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// "form.pdf" → "PDF", "guide.docx" → "DOCX" (shorter than the content type)
function typeLabel(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "FILE" : filename.slice(dot + 1).toUpperCase();
}

export function DocumentList({
  documents,
  loading,
  error,
  deleting,
  onDelete,
  renderActions,
}: Props) {
  const handleDelete = async (document: StoredDocument) => {
    if (!window.confirm(`Delete ${document.filename}? This can't be undone from the app.`)) return;
    try {
      await onDelete(document.name);
      toast.success(`${document.filename} deleted`);
    } catch (e) {
      toast.error(`${document.filename}: ${(e as Error).message}`);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Documents ({documents.length})</CardTitle>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-sm text-destructive">Couldn't load documents: {error}</p>
        ) : loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : documents.length === 0 ? (
          <p className="text-sm text-muted-foreground">No documents yet. Upload the first one.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Size</TableHead>
                <TableHead>Uploaded</TableHead>
                <TableHead className="text-right">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents.map((document) => (
                <TableRow key={document.name}>
                  <TableCell className="flex items-center gap-2 font-medium">
                    {document.content_type === "application/pdf" ? (
                      <FileTextIcon className="size-4 text-muted-foreground" />
                    ) : (
                      <ImageIcon className="size-4 text-muted-foreground" />
                    )}
                    {document.filename}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{typeLabel(document.filename)}</Badge>
                  </TableCell>
                  <TableCell className="text-right">{formatSize(document.size)}</TableCell>
                  <TableCell>{new Date(document.uploaded_at).toLocaleString()}</TableCell>
                  <TableCell className="flex items-center justify-end gap-1">
                    {renderActions?.(document)}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Delete ${document.filename}`}
                      disabled={deleting !== null}
                      onClick={() => void handleDelete(document)}
                    >
                      <Trash2Icon className="text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
