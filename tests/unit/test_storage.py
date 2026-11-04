import hashlib
import json
import pytest
from app.storage.service import StorageError, StorageService

def service(tmp_path, **kwargs):
    s = StorageService(tmp_path, **kwargs)
    s.create_bucket("bucket")
    return s

def write(path, data):
    p = path / "input"
    p.write_bytes(data)
    return p

def test_bucket_lifecycle_and_object_replacement(tmp_path):
    s = service(tmp_path)
    with pytest.raises(StorageError, match="exist"):
        s.delete_bucket("missing")
    first = s.put_object("bucket", "key", write(tmp_path, b"one"), "text/plain", {"x": "y"})
    old_id = first["storage_id"]
    second = s.put_object("bucket", "key", write(tmp_path, b"two"))
    assert second["size"] == 3 and second["etag"] == '"'+hashlib.md5(b"two").hexdigest()+'"'
    assert not s.files.final_path(old_id).exists()
    with pytest.raises(StorageError) as exc:
        s.delete_bucket("bucket")
    assert exc.value.code == "BucketNotEmpty"
    s.delete_object("bucket", "key")
    s.delete_bucket("bucket")

def test_object_limit_cleans_temp_and_copy_preserves_metadata(tmp_path):
    s = service(tmp_path, max_object_size=3)
    too_big = write(tmp_path, b"1234")
    with pytest.raises(StorageError) as exc:
        s.put_object("bucket", "large", too_big)
    assert exc.value.code == "EntityTooLarge" and not too_big.exists()
    source = write(tmp_path, b"abc")
    s.put_object("bucket", "source", source, "text/custom", {"kind": "copy"})
    copied = s.copy_object("bucket", "copy", "bucket", "source")
    assert copied["content_type"] == "text/custom"
    assert json.loads(copied["metadata"]) == {"kind": "copy"}

def test_multipart_complete_abort_and_cleanup(tmp_path):
    s = service(tmp_path, max_object_size=10)
    uid = s.initiate("bucket", "multi", "text/plain", {"a": "b"})
    p1 = write(tmp_path, b"ab")
    e1 = s.upload_part(uid, 1, p1)
    p2 = write(tmp_path, b"cd")
    e2 = s.upload_part(uid, 2, p2)
    assert [p["part_number"] for p in s.parts(uid)[1]] == [1, 2]
    obj = s.complete(uid, [(1, e1), (2, e2)])
    assert obj["size"] == 4 and obj["etag"].endswith("-2\"")
    assert not (s.files.multipart / uid).exists()
    uid2 = s.initiate("bucket", "aborted")
    s.abort(uid2)
    with pytest.raises(StorageError) as exc:
        s.parts(uid2)
    assert exc.value.code == "NoSuchUpload"

def test_multipart_total_limit_and_invalid_upload_cleanup(tmp_path):
    s = service(tmp_path, max_object_size=3)
    uid = s.initiate("bucket", "too-large")
    s.upload_part(uid, 1, write(tmp_path, b"12"))
    s.upload_part(uid, 2, write(tmp_path, b"34"))
    with pytest.raises(StorageError) as exc:
        s.complete(uid, [(1, s.parts(uid)[1][0]["etag"]), (2, s.parts(uid)[1][1]["etag"])])
    assert exc.value.code == "EntityTooLarge"
    invalid = write(tmp_path, b"x")
    with pytest.raises(StorageError) as exc:
        s.upload_part("invalid", 1, invalid)
    assert exc.value.code == "NoSuchUpload" and not invalid.exists()
