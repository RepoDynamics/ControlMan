

class IssueFormGenerator:

    def __init__(self, metadata: dict, reader: MetaReader, logger: Logger = None):
        if not isinstance(reader, MetaReader):
            raise TypeError(f"reader must be of type MetaReader, not {type(reader)}")
        self._reader = reader
        self._logger = logger or reader.logger
        self._meta = metadata
        return

