from dataclasses import dataclass


@dataclass
class TranslateDeps:
    target_lang: str
    source_lang: str
