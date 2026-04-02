from pathlib import Path


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers = []

    def register(self, parser) -> None:
        self._parsers.append(parser)

    def get_parser(self, file_path: Path):
        for parser in self._parsers:
            if parser.supports(file_path):
                return parser
        return None


parser_registry = ParserRegistry()
