from ..model import Bill
from . import nrg
from .common import ParseError

# Νέος πάροχος (π.χ. dei): module με matches()/parse() και προσθήκη εδώ.
PARSERS = [nrg]

__all__ = ["ParseError", "parse_bill"]


def parse_bill(text: str) -> Bill | None:
    for parser in PARSERS:
        if parser.matches(text):
            return parser.parse(text)
    return None
