import { FileTextIcon } from "lucide-react";
import { documentFileUrl } from "@/api/documents";
import type { Source } from "@/api/rules";
import { DocumentViewer } from "@/components/documents/DocumentViewer/DocumentViewer";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { pagesText } from "../ruleText";

// A rule's quote: click it to open the guideline in a drawer, at the quote, highlighted
export function SourceQuote({ source }: { source: Source }) {
  return (
    <Sheet>
      <SheetTrigger
        render={
          <button
            type="button"
            className="group w-full rounded-md border border-dashed bg-muted/30 px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:border-primary hover:bg-muted"
            title="Show it in the document"
          />
        }
      >
        <span className="line-clamp-3 italic">“{source.quote}”</span>
        <span className="mt-1 flex items-center gap-1 font-medium text-foreground/70 group-hover:text-primary">
          <FileTextIcon className="size-3.5" /> {pagesText(source)} · show in document
        </span>
      </SheetTrigger>
      <SheetContent side="right" className="w-full gap-0 sm:max-w-3xl">
        <SheetHeader className="border-b">
          <SheetTitle>{source.document}</SheetTitle>
          <SheetDescription>
            {source.page
              ? `The quote is highlighted on ${pagesText(source)}.`
              : "The quote wasn't found in this document."}
          </SheetDescription>
        </SheetHeader>
        <div className="min-h-0 flex-1">
          <DocumentViewer
            url={documentFileUrl("requirement", source.document)}
            quote={source.quote}
            firstPage={source.page}
            lastPage={source.last_page}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
