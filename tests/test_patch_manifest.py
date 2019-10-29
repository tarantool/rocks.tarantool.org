import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import patch_manifest  # noqa


def test_add_all():
    with open('tests/manifest') as file:
        _, rock = patch_manifest(file.read(), ' ', 'cartridge-1.1.1-1.all.rock', False, 'add')

    with open('tests/manifest_added_all_rock') as file:
        assert rock == file.read()


def test_add_existed_all():
    with open('tests/manifest_added_all_rock') as file:
        _, rock = patch_manifest(file.read(), ' ', 'cartridge-1.1.1-1.all.rock', False, 'add')

    with open('tests/manifest_added_all_rock') as file:
        assert rock == file.read()


def test_remove_all():
    with open('tests/manifest_added_all_rock') as file:
        _, rock = patch_manifest(file.read(), ' ', 'cartridge-1.1.1-1.all.rock', False, 'remove')

    with open('tests/manifest') as file:
        assert rock == file.read()


def test_remove_non_existed():
    with open('tests/manifest') as file:
        _, rock = patch_manifest(file.read(), ' ', 'cartridge-1.1.1-1.all.rock', False, 'remove')

    with open('tests/manifest') as file:
        assert rock == file.read()
