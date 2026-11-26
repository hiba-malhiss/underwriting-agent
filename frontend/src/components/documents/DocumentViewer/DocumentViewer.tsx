import { useCallback, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import { findQuote, markWords, type Highlight } from "./highlight";

// Must be set in the module that renders <Document> (react-pdf's README)
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

interface Props {
  url: string;
  quote?: string;
  firstPage?: number | null; // where the quote starts…
  lastPage?: number | null; // …and ends, if it runs onto the next page
}

// A PDF, every page, with `quote` highlighted and scrolled into view
export function DocumentViewer({ url, quote, firstPage, lastPage }: Props) {
  const [pageCount, setPageCount] = useState(0);
  const [width, setWidth] = useState<number>();
  const container = useRef<HTMLDivElement | null>(null);

  // Pages fill the drawer's width (measured once it's on screen)
  const measure = useCallback((element: HTMLDivElement | null) => {
    container.current = element;
    if (element) setWidth(element.clientWidth);
  }, []);

  const end = lastPage ?? firstPage;
  const hasQuote = (page: number) => !!quote && !!firstPage && page >= firstPage && page <= end!;

  return (
    <div ref={measure} className="h-full overflow-y-auto bg-muted/40">
      <Document
        file={url}
        onLoadSuccess={({ numPages }) => setPageCount(numPages)}
        loading={<p className="p-4 text-sm text-muted-foreground">Loading the document…</p>}
        error={
          <p className="p-4 text-sm text-destructive">This document can't be shown (PDF only).</p>
        }
      >
        {width &&
          Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => (
            <DocumentPage
              key={page}
              page={page}
              width={width - 32}
              quote={hasQuote(page) ? quote : undefined}
              scrollHere={page === firstPage}
            />
          ))}
      </Document>
    </div>
  );
}

interface PageProps {
  page: number;
  width: number;
  quote?: string;
  scrollHere: boolean;
}

function DocumentPage({ page, width, quote, scrollHere }: PageProps) {
  const [highlight, setHighlight] = useState<Highlight>();
  const element = useRef<HTMLDivElement>(null);

  return (
    <div ref={element} className="mx-4 my-4 shadow-sm">
      <Page
        pageNumber={page}
        width={width}
        // pdf.js reads the page's text first; the quote is found in it, then marked as it's drawn
        onGetTextSuccess={({ items }) => {
          if (quote)
            setHighlight(
              findQuote(
                items.map((item) => ("str" in item ? item.str : "")),
                quote,
              ),
            );
        }}
        customTextRenderer={({ str, itemIndex }) => markWords(str, highlight?.get(itemIndex))}
        onRenderTextLayerSuccess={() => {
          if (!scrollHere) return;
          const mark = element.current?.querySelector("mark") ?? element.current;
          mark?.scrollIntoView({ block: "center" });
        }}
      />
    </div>
  );
}
