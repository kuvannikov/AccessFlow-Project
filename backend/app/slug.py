import re
import unicodedata

CYRILLIC = dict(
    zip(
        "абвгдежзийклмнопрстуфхцчшщъыьэюя",
        [
            "a",
            "b",
            "v",
            "g",
            "d",
            "e",
            "zh",
            "z",
            "i",
            "y",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "r",
            "s",
            "t",
            "u",
            "f",
            "h",
            "ts",
            "ch",
            "sh",
            "sch",
            "",
            "y",
            "",
            "e",
            "yu",
            "ya",
        ],
    )
)
CYRILLIC["ё"] = "yo"
CYRILLIC.update({"ґ": "g", "є": "ye", "і": "i", "ї": "yi", "ў": "u"})
SEPARATORS = " -'’"


def slug_part(value: str) -> str:
    parts = []
    for char in unicodedata.normalize("NFC", value.strip()).lower():
        if char in CYRILLIC:
            parts.append(CYRILLIC[char])
        elif "a" <= char <= "z" or "0" <= char <= "9":
            parts.append(char)
        elif char in SEPARATORS:
            parts.append("-")
        elif char.isalpha():
            raise ValueError("Имя содержит буквы, для которых нельзя создать slug")
        else:
            raise ValueError("В имени допустимы буквы, цифры, пробел, дефис и апостроф")
    return re.sub(r"-+", "-", "".join(parts)).strip("-")


def base_slug(first_name: str, last_name: str) -> str:
    first = slug_part(first_name)[:80].rstrip("-")
    last = slug_part(last_name)[:80].rstrip("-")
    if not first or not last:
        raise ValueError("Из имени и фамилии нельзя создать slug")
    return f"{first}.{last}"
