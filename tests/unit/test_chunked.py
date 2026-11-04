import pytest
from app.api.chunked import AwsChunkedDecoder, ChunkedDecodeError

SIG = "chunk-signature=" + "a" * 64


def signed_body(*parts, trailer=True):
    body = b"".join(f"{len(p):x};{SIG}\r\n".encode() + p + b"\r\n" for p in parts)
    body += f"0;{SIG}\r\n".encode()
    if trailer:
        body += b"x-amz-checksum-crc32:kiJl9A==\r\nx-amz-trailer-signature:" + b"b" * 64 + b"\r\n"
    return body + b"\r\n"


def decode(body, step=None):
    decoder = AwsChunkedDecoder()
    out = b""
    if step is None:
        out = decoder.feed(body)
    else:
        for i in range(0, len(body), step):
            out += decoder.feed(body[i:i + step])
    decoder.close()
    return out


def test_signed_chunks_with_checksum_trailer():
    assert decode(signed_body(b"hello ", b"world")) == b"hello world"


def test_unsigned_chunks_without_signatures():
    assert decode(b"5\r\nhello\r\n0\r\n\r\n") == b"hello"


@pytest.mark.parametrize("step", [1, 2, 3, 7, 64])
def test_any_split_of_the_stream_decodes_the_same(step):
    payload = bytes(range(256)) * 5
    assert decode(signed_body(payload[:700], payload[700:]), step) == payload


def test_data_that_looks_like_framing_is_kept():
    payload = b"10;chunk-signature=x\r\nnot a header\r\n0\r\n\r\n"
    assert decode(signed_body(payload)) == payload


def test_empty_object():
    assert decode(signed_body()) == b""


def test_truncated_body_is_rejected():
    decoder = AwsChunkedDecoder()
    decoder.feed(signed_body(b"hello")[:20])
    with pytest.raises(ChunkedDecodeError):
        decoder.close()


def test_bad_chunk_size_is_rejected():
    with pytest.raises(ChunkedDecodeError):
        AwsChunkedDecoder().feed(b"zz\r\nhello\r\n")


def test_missing_chunk_terminator_is_rejected():
    with pytest.raises(ChunkedDecodeError):
        AwsChunkedDecoder().feed(b"5\r\nhelloXX0\r\n\r\n")
