"""Read text: finding a quote and its page(s), including a paragraph split across two pages."""

from app.infrastructure.document_reader import DocumentText, PageSpan, _readable_checkboxes

PAGE_1 = "1. Age limits\nApplicants over 65 years of age are\n"
PAGE_2 = "not eligible for new coverage.\n2. Smoking\nSmokers are referred for review."
DOCUMENT = DocumentText(
    content=PAGE_1 + PAGE_2,
    pages=[
        PageSpan(1, 0, len(PAGE_1)),
        PageSpan(2, len(PAGE_1), len(PAGE_1) + len(PAGE_2)),
    ],
)


def test_a_quote_on_one_page():
    assert DOCUMENT.locate("Smokers are referred for review.") == (2, 2)


# The sentence starts on page 1 and ends on page 2: it still matches, with both pages
def test_a_quote_split_across_two_pages():
    quote = "Applicants over 65 years of age are not eligible for new coverage."
    assert DOCUMENT.locate(quote) == (1, 2)


# The LLM's spacing and quote marks can differ from the PDF's; the words must still match
def test_spaces_line_breaks_and_curly_quotes_do_not_matter():
    assert DOCUMENT.locate("Applicants   over 65\nyears of age") == (1, 1)
    curly = DocumentText("Applicant’s age", [PageSpan(1, 0, 15)])
    assert curly.locate("Applicant's age") == (1, 1)


# A made-up quote (or one with a changed number) is not found
def test_a_quote_that_is_not_in_the_text():
    assert DOCUMENT.locate("Applicants over 70 years of age are not eligible") is None
    assert DOCUMENT.locate("") is None


def test_page_markers_show_where_each_page_starts():
    marked = DOCUMENT.with_page_markers()
    assert marked.startswith("[page 1]\n1. Age limits")
    assert "\n[page 2]\nnot eligible for new coverage." in marked


# A ticked box matters ("Do you smoke? [x] Yes"): it's kept readable, and page offsets don't move
def test_checkboxes_stay_readable_without_moving_offsets():
    content = "Do you smoke? :selected: Yes :unselected: No"
    readable = _readable_checkboxes(content)
    assert readable.split() == ["Do", "you", "smoke?", "[x]", "Yes", "[", "]", "No"]
    assert len(readable) == len(content)
    assert readable.index("Yes") == content.index("Yes")
    assert DocumentText(readable, [PageSpan(1, 0, len(readable))]).locate("[x] Yes") == (1, 1)


# Layout reads bullet points as ticked boxes, so "[x]" can sit inside a sentence: still matches
def test_checkbox_marks_inside_a_sentence_do_not_break_a_quote():
    text = "with proof [x]        of enrolment.\nNext point"
    document = DocumentText(text, [PageSpan(1, 0, len(text))])
    assert document.locate("with proof of enrolment.") == (1, 1)


# Part of a sentence, ended with a "." by the LLM, still matches; changed words still don't
def test_punctuation_at_the_edges_of_a_quote_does_not_matter():
    text = "A spouse requires a marriage certificate and children require a birth certificate."
    document = DocumentText(text, [PageSpan(1, 0, len(text))])
    assert document.locate("A spouse requires a marriage certificate.") == (1, 1)
    assert document.locate("A spouse needs a marriage certificate.") is None


# Two bullets quoted together: Layout reads the bullet between them as a stray "." (or "•")
def test_bullets_between_quoted_lines_do_not_break_a_quote():
    text = "age.\n. Principal: 18 to 64 years.\n. Spouse: 18 to 64 years.\n• Child: up to 21."
    document = DocumentText(text, [PageSpan(1, 0, len(text))])
    quote = "Principal: 18 to 64 years. Spouse: 18 to 64 years. Child: up to 21."
    assert document.locate(quote) == (1, 1)


# A dot that isn't alone still counts: numbers and sentence ends must match exactly
def test_dots_inside_numbers_still_count():
    text = "HbA1c above 7.5% is referred."
    document = DocumentText(text, [PageSpan(1, 0, len(text))])
    assert document.locate("HbA1c above 7.5%") == (1, 1)
    assert document.locate("HbA1c above 75%") is None
