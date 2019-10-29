import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import patch_manifest  # noqa


def test_add_all():
    with open('tests/manifest') as file:
        _, rock = patch_manifest(file.read(), ' ', 'cartridge-1.1.1-1.all.rock', False, 'add')

    with open('tests/manifest_all') as file:
        assert rock == file.read()


def test_add_existed_all():
    with open('tests/manifest_all') as file:
        _, rock = patch_manifest(file.read(), ' ', 'cartridge-1.1.1-1.all.rock', False, 'add')

    with open('tests/manifest_all') as file:
        assert rock == file.read()


def test_add_src():
    with open('tests/manifest_all') as file:
        _, rock = patch_manifest(file.read(), ' ', 'cartridge-1.1.1-1.src.rock', False, 'add')

    with open('tests/manifest_all_src') as file:
        assert rock == file.read()


def test_add_x86():
    with open('tests/manifest_all_src') as file:
        _, rock = patch_manifest(file.read(), ' ', 'tarantool-curl-2.3.1-1.x86.rock', False, 'add')

    with open('tests/manifest_all_src_x86') as file:
        assert rock == file.read()


def test_add_version():
    with open('tests/avro-schema-2.2.1-5.rockspec') as file:
        rockspec = file.read()

    with open('tests/manifest') as file:
        _, rock = patch_manifest(file.read(), rockspec, 'avro-schema-2.2.1-5.rockspec', True, 'add')

    with open('tests/manifest_version') as file:
        assert rock == file.read()


def test_removed_version():
    with open('tests/manifest_version') as file:
        _, rock = patch_manifest(file.read(), '', 'cartridge-1.1.0-1.all.rock', False, 'remove')

    with open('tests/manifest_removed_version') as file:
        assert rock == file.read()


def test_remove_all():
    with open('tests/manifest_all') as file:
        _, rock = patch_manifest(file.read(), ' ', 'cartridge-1.1.1-1.all.rock', False, 'remove')

    with open('tests/manifest') as file:
        assert rock == file.read()


def test_remove_non_existed():
    with open('tests/manifest') as file:
        _, rock = patch_manifest(file.read(), ' ', 'cartridge-1.1.1-1.all.rock', False, 'remove')

    with open('tests/manifest') as file:
        assert rock == file.read()
