import unicodedata


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)

    return "".join(
        char
        for char in text
        if unicodedata.category(char) != "Mn"
    )
