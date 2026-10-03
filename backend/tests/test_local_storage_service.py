import pytest

from app.services.local_storage_service import LocalStorageService


@pytest.mark.parametrize(
    "path",
    [
        "../secret",
        "/tmp/secret",
        "app.db",
        "uploads",
        "uploads/../../secret",
        "uploads/../figures/a",
        "uploads/..\\secret",
        "uploads/a\x00",
    ],
)
def test_storage_rejects_uncontained_paths(tmp_path, path):
    storage = LocalStorageService(tmp_path)
    for operation in (
        storage.get_file,
        storage.get_file_path,
        storage.delete_file,
        storage.file_exists,
    ):
        with pytest.raises(ValueError):
            operation(path)


def test_storage_roundtrip_and_atomic_cleanup(tmp_path):
    storage = LocalStorageService(tmp_path)
    for save in (storage.save_upload, storage.save_figure, storage.save_export):
        path = save("project/resource.bin", b"original")
        assert storage.get_file(path) == b"original"
        save("project/resource.bin", b"replacement")
        assert storage.get_file(path) == b"replacement"
        assert storage.file_exists(path)
        storage.delete_file(path)
        assert not storage.file_exists(path)
    assert not list(tmp_path.rglob(".pending-*"))


def test_storage_rejects_symlink_escape(tmp_path):
    storage = LocalStorageService(tmp_path / "data")
    outside = tmp_path / "outside"
    outside.mkdir()
    (storage.uploads_dir / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        storage.save_upload("link/secret.txt", b"bad")
    assert not (outside / "secret.txt").exists()


def test_static_data_directory_is_not_mounted():
    from app.main import create_app

    assert not any(getattr(route, "path", None) == "/data" for route in create_app().routes)
