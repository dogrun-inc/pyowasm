import pytest
import os
from pyowasm.engine.vfs import VFSManager

def test_vfs_manager_write_and_read(tmp_path):
    filename = str(tmp_path / 'test.txt')
    content = 'Hello VFS!'
    VFSManager.write_to_vfs(filename, content)
    assert os.path.exists(filename)
    read_content = VFSManager.read_from_vfs(filename)
    assert read_content == content

def test_vfs_manager_read_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        VFSManager.read_from_vfs('non_existent_file.txt')
