import { FileTextIcon, ImageIcon } from "lucide-react";
import type { StoredDocument } from "@/api/types";
import { Badge } from "@/components/ui/badge";
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

export function DocumentList({ documents, loading, error }: Props) {
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
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
