import { useRef } from "react";
import { UploadIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { DOCUMENT_FILE_TYPES, MAX_UPLOAD_MB } from "@/config";

interface Props {
  uploading: boolean;
  onUpload: (file: File) => Promise<unknown>;
}

// The same rules the backend enforces, checked here first so the user gets the reason at once
function rejection(file: File): string | null {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!DOCUMENT_FILE_TYPES.includes(extension)) {
    return `Unsupported file type. Allowed: ${DOCUMENT_FILE_TYPES.join(", ")}`;
  }
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `The file is larger than ${MAX_UPLOAD_MB} MB`;
  return null;
}

export function DocumentUpload({ uploading, onUpload }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList | null) => {
    for (const file of Array.from(files ?? [])) {
      const reason = rejection(file);
      if (reason) {
        toast.error(`${file.name}: ${reason}`);
        continue;
      }
      try {
        await onUpload(file);
        toast.success(`${file.name} uploaded`);
      } catch (e) {
        toast.error(`${file.name}: ${(e as Error).message}`);
      }
    }
    if (inputRef.current) inputRef.current.value = ""; // allow picking the same file again
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload documents</CardTitle>
        <CardDescription>
          Application form, medical reports, ID. PDF or image, up to {MAX_UPLOAD_MB} MB each.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={DOCUMENT_FILE_TYPES.join(",")}
          className="hidden"
          onChange={(event) => void handleFiles(event.target.files)}
        />
        <Button disabled={uploading} onClick={() => inputRef.current?.click()}>
          <UploadIcon />
          {uploading ? "Uploading…" : "Choose files"}
        </Button>
      </CardContent>
    </Card>
  );
}
