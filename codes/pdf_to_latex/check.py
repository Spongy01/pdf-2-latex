# read a text file and print its content
with open(
    "files/data-science-book_book/inputs/data-science-book.tex",
    "r",
    encoding="utf-8",
) as f:
    content = f.read()
    print(content[756593 - 50 : 756593 + 1])
