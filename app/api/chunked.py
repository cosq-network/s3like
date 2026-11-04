"""Decoder for the ``aws-chunked`` request bodies that AWS SDKs send for streaming and checksummed uploads."""

MAX_LINE = 4096


class ChunkedDecodeError(ValueError):
    pass


class AwsChunkedDecoder:
    """Strips aws-chunked framing and returns only the object bytes.

    The body is a series of ``<hex size>[;chunk-signature=...]\\r\\n<data>\\r\\n`` chunks, a zero-size last chunk, then
    optional trailers (for example ``x-amz-checksum-crc32`` and ``x-amz-trailer-signature``) and a blank line. Chunk
    signatures and trailers are not verified: the request itself is authenticated by its headers, and this store is
    meant for development and tests.
    """

    def __init__(self):
        self._buffer = bytearray()
        self._state = 'size'
        self._remaining = 0

    def feed(self, data):
        self._buffer += data
        out = bytearray()
        while True:
            if self._state == 'data':
                if not self._buffer:
                    break
                taken = bytes(self._buffer[:self._remaining])
                out += taken
                del self._buffer[:len(taken)]
                self._remaining -= len(taken)
                if self._remaining:
                    break
                self._state = 'data_end'
            elif self._state == 'data_end':
                if len(self._buffer) < 2:
                    break
                if self._buffer[:2] != b'\r\n':
                    raise ChunkedDecodeError('Malformed chunk terminator.')
                del self._buffer[:2]
                self._state = 'size'
            elif self._state in ('size', 'trailer'):
                end = self._buffer.find(b'\r\n')
                if end < 0:
                    if len(self._buffer) > MAX_LINE:
                        raise ChunkedDecodeError('Chunk header is too long.')
                    break
                line = bytes(self._buffer[:end])
                del self._buffer[:end + 2]
                if self._state == 'size':
                    try:
                        size = int(line.split(b';', 1)[0].strip(), 16)
                    except ValueError:
                        raise ChunkedDecodeError('Malformed chunk size.') from None
                    if size < 0:
                        raise ChunkedDecodeError('Malformed chunk size.')
                    if size == 0:
                        self._state = 'trailer'
                    else:
                        self._remaining = size
                        self._state = 'data'
                elif line == b'':
                    self._state = 'done'
            else:
                self._buffer.clear()
                break
        return bytes(out)

    def close(self):
        """Raises when the body ended before the last (zero-size) chunk."""
        if self._state not in ('trailer', 'done'):
            raise ChunkedDecodeError('The request body ended before the last chunk.')
