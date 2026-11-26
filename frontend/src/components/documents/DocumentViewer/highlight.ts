// Finding a quote in a PDF page's text, to highlight it.
//
// pdf.js gives a page's text as "items" (usually one line or a part of one). The quote is compared
// word by word, ignoring case, punctuation, bullets and line breaks (like the backend's quote
// check), and the longest run of the quote's words found on the page is highlighted. So a quote
// that runs onto the next page is highlighted in two parts, one on each page.

const WORD = /\S+/g;

// Which words to highlight: item index → positions of its words (0, 1, 2… in that item)
export type Highlight = Map<number, Set<number>>;

function normalize(word: string): string {
  return word.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

export function findQuote(items: string[], quote: string): Highlight {
  const pageWords: { item: number; position: number; word: string }[] = [];
  items.forEach((text, item) => {
    [...text.matchAll(WORD)].forEach((match, position) => {
      const word = normalize(match[0]);
      if (word) pageWords.push({ item, position, word }); // "•", "[x]" alone don't count
    });
  });
  const quoteWords = (quote.match(WORD) ?? []).map(normalize).filter(Boolean);

  // The longest run of words the page and the quote share (longest common substring, by words)
  let longest = 0;
  let end = 0;
  let previous = new Array<number>(quoteWords.length + 1).fill(0);
  for (let i = 1; i <= pageWords.length; i++) {
    const current = new Array<number>(quoteWords.length + 1).fill(0);
    for (let j = 1; j <= quoteWords.length; j++) {
      if (pageWords[i - 1].word !== quoteWords[j - 1]) continue;
      current[j] = previous[j - 1] + 1;
      if (current[j] > longest) [longest, end] = [current[j], i];
    }
    previous = current;
  }

  const highlight: Highlight = new Map();
  // A couple of common words ("the", "of") aren't the quote
  if (longest < Math.min(3, quoteWords.length)) return highlight;
  for (const { item, position } of pageWords.slice(end - longest, end)) {
    highlight.set(item, (highlight.get(item) ?? new Set()).add(position));
  }
  return highlight;
}

const ESCAPED: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
};

// One text item as HTML, with its highlighted words in <mark> (the PDF's text is escaped)
export function markWords(text: string, positions: Set<number> | undefined): string {
  let position = 0;
  return text.replace(WORD, (word) => {
    const html = word.replace(/[&<>"]/g, (c) => ESCAPED[c]);
    return positions?.has(position++) ? `<mark>${html}</mark>` : html;
  });
}
