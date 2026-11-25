from ..model import Bill
from . import dei, nrg
from .common import ParseError

# Νέος πάροχος: module με matches()/parse() και προσθήκη εδώ.
PARSERS = [nrg, dei]

__all__ = ["ParseError", "parse_bill"]


def parse_bill(text: str) -> Bill | None:
    for parser in PARSERS:
        if parser.matches(text):
            return parser.parse(text)
    return None
