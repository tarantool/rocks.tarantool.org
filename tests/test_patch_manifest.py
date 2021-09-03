import os
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from app import patch_manifest, InvalidUsage  # noqa
from textwrap import dedent

def test_override():
    manifest = """
        commands = {}
        modules = {}
        repository = {}
    """

    manifest_expected = dedent("""\
        commands = {}
        modules = {}
        repository = {
            cartridge = {
                ["scm-1"] = {
                    {
                        arch = "all"
                    }
                }
            }
        }
    """)

    msg, manifest = patch_manifest(manifest, 'cartridge-scm-1.all.rock')
    assert msg == "rock entry was successfully added to manifest"
    assert manifest == manifest_expected

    msg, manifest = patch_manifest(manifest, 'cartridge-scm-1.all.rock')
    assert msg == "rock entry was successfully added to manifest"
    assert manifest == manifest_expected

def test_multiarch():
    manifest = """
        commands = {}
        modules = {}
        repository = {}
    """
    manifest_expected = dedent("""\
        commands = {}
        modules = {}
        repository = {
            cartridge = {
                ["6.6.6-1"] = {
                    {
                        arch = "src"
                    },
                    {
                        arch = "all"
                    }
                }
            }
        }
    """)

    msg, patched_manifest_1 = patch_manifest(manifest, 'cartridge-6.6.6-1.src.rock')
    assert msg == "rock entry was successfully added to manifest"

    msg, patched_manifest_2 = patch_manifest(patched_manifest_1, 'cartridge-6.6.6-1.src.rock')
    assert msg == "the rock already exists"
    assert patched_manifest_2 == None

    msg, patched_manifest_3 = patch_manifest(patched_manifest_1, 'cartridge-6.6.6-1.all.rock')
    assert msg == "rock entry was successfully added to manifest"
    assert patched_manifest_3 == manifest_expected

    msg, patched_manifest_4 = patch_manifest(patched_manifest_3, 'cartridge-6.6.6-1.all.rock')
    assert msg == "the rock already exists"
    assert patched_manifest_4 == None


def test_multiversion():
    manifest = """
        commands = {}
        modules = {}
        repository = {}
    """
    manifest_expected = dedent("""\
        commands = {}
        modules = {}
        repository = {
            cartridge = {
                ["6.6.6-1"] = {
                    {
                        arch = "all"
                    }
                },
                ["dev-1"] = {
                    {
                        arch = "all"
                    }
                }
            }
        }
    """)

    msg, manifest = patch_manifest(manifest, 'cartridge-6.6.6-1.all.rock')
    assert msg == "rock entry was successfully added to manifest"
    msg, manifest = patch_manifest(manifest, 'cartridge-dev-1.all.rock')
    assert msg == "rock entry was successfully added to manifest"

    assert manifest == manifest_expected

def test_rockspec():
    manifest = """
        commands = {}
        modules = {}
        repository = {}
    """

    manifest_expected = dedent("""\
        commands = {}
        modules = {}
        repository = {
            ["foo-bar"] = {
                ["5.4.3.2-1"] = {
                    {
                        arch = "rockspec"
                    }
                },
                ["dev-1"] = {
                    {
                        arch = "rockspec"
                    }
                }
            }
        }
    """)

    rockspec = """\
        package = 'foo-bar'
        version = 'dev-1'
    """
    msg, patched_manifest_1 = patch_manifest(manifest, 'foo-bar-dev-1.rockspec',
        rock_content = rockspec)
    assert msg == "rock entry was successfully added to manifest"

    rockspec = """\
        package = 'foo-bar'
        version = '5.4.3.2-1'
    """
    msg, patched_manifest_2 = patch_manifest(patched_manifest_1, 'foo-bar-5.4.3.2-1.rockspec',
                                   rock_content = rockspec)
    assert msg == "rock entry was successfully added to manifest"

    assert patched_manifest_2 == manifest_expected

    msg, patched_manifest_3 = patch_manifest(patched_manifest_2, 'foo-bar-dev-2.rockspec', rock_content = rockspec)
    assert msg == "rockspec name does not match package or version"

    msg, patched_manifest_4 = patch_manifest(patched_manifest_2, 'foo-baz-dev-1.rockspec', rock_content = rockspec)
    assert msg == "rockspec name does not match package or version"


def test_multipackage():
    manifest = """
        commands = {}
        modules = {}
        repository = {}
    """

    rockspec = """\
        package = 'fizz-buzz'
        version = 'dev-2'
    """
    msg, manifest = patch_manifest(manifest, 'fizz-buzz-dev-2.rockspec',
        rock_content = rockspec)
    assert msg == "rock entry was successfully added to manifest"

    rockspec = """\
        package = 'fizz-buzz'
        version = '0.0.0-2'
    """
    msg, manifest = patch_manifest(manifest, 'fizz-buzz-0.0.0-2.rockspec',
        rock_content = rockspec)
    assert msg == "rock entry was successfully added to manifest"

    msg, manifest = patch_manifest(manifest, 'mymodule-0.0.0-2.linux-x86_64.rock')
    assert msg == "rock entry was successfully added to manifest"

    assert manifest == dedent("""\
        commands = {}
        modules = {}
        repository = {
            ["fizz-buzz"] = {
                ["0.0.0-2"] = {
                    {
                        arch = "rockspec"
                    }
                },
                ["dev-2"] = {
                    {
                        arch = "rockspec"
                    }
                }
            },
            mymodule = {
                ["0.0.0-2"] = {
                    {
                        arch = "linux-x86_64"
                    }
                }
            }
        }
    """)

def test_remove_one():

    manifest = dedent("""\
        commands = {}
        modules = {}
        repository = {
            ["foo-bar"] = {
                ["3.2-1"] = {
                    {
                        arch = "rockspec"
                    },
                    {
                        arch = "all"
                    }    
                },
                ["dev-1"] = {
                    {
                        arch = "rockspec"
                    }
                }
            }
        }
    """)

    manifest_expected = dedent("""\
        commands = {}
        modules = {}
        repository = {
            ["foo-bar"] = {
                ["3.2-1"] = {
                    {
                        arch = "all"
                    }
                },
                ["dev-1"] = {
                    {
                        arch = "rockspec"
                    }
                }
            }
        }
    """)

    msg, patched_manifest_1 = patch_manifest(manifest, 'foo-bar-3.2-1.rockspec',
        action = 'remove')
    assert msg == "rock was successfully removed from manifest"
    assert patched_manifest_1 == manifest_expected

    msg, patched_manifest_2 = patch_manifest(patched_manifest_1, 'foo-bar-dev-1.all.rock', action='remove')
    assert msg == "rock architecture was not found in manifest"
    assert patched_manifest_2 == None

    msg, patched_manifest_3 = patch_manifest(patched_manifest_1, 'foo-bar-3.2-1.rockspec', action='remove')
    assert msg == "rock architecture was not found in manifest"

    msg, patched_manifest_4 = patch_manifest(patched_manifest_1, 'foo-bar-3.3-1.rockspec', action='remove')
    assert msg == "rock version was not found in manifest"

    msg, patched_manifest_5 = patch_manifest(patched_manifest_1, 'foo-bar-dev-1.all.rock', action='remove')
    assert msg == "rock architecture was not found in manifest"
    assert patched_manifest_5 == None

    msg, patched_manifest_6 = patch_manifest(patched_manifest_1, 'foo-bar-3.2-1.rockspec', action='remove')
    assert msg == "rock architecture was not found in manifest"
    assert patched_manifest_6 == None

    msg, patched_manifest_7 = patch_manifest(patched_manifest_1, 'foo-bar-3.3-1.rockspec', action = 'remove')
    assert msg == "rock version was not found in manifest"
    assert patched_manifest_7 == None

    msg, patched_manifest_8 = patch_manifest(patched_manifest_1, 'foo-baz-dev-1.rockspec', action = 'remove')
    assert msg == "rock was not found in manifest"
    assert patched_manifest_8 == None

    msg, patched_manifest_9 = patch_manifest(patched_manifest_1, 'foo.rockspec', action = 'remove')
    assert msg == "filename parsing error"
    assert patched_manifest_9 == None


def test_remove_last():
    manifest = dedent("""\
        commands = {}
        modules = {}
        repository = {
            ["foo-bar"] = {
                ["3.2-1"] = {
                    {
                        arch = "all"
                    }
                },
                ["dev-1"] = {
                    {
                        arch = "rockspec"
                    }
                }
            }
        }
    """)

    manifest_expected = dedent("""\
        commands = {}
        modules = {}
        repository = {
            ["foo-bar"] = {
                ["dev-1"] = {
                    {
                        arch = "rockspec"
                    }
                }
            }
        }
    """)

    msg, patched_manifest_1 = patch_manifest(manifest, 'foo-bar-3.2-1.all.rock',
        action = 'remove')
    assert msg == "rock was successfully removed from manifest"
    assert patched_manifest_1 == manifest_expected

    msg, patched_manifest_2 = patch_manifest(patched_manifest_1, 'foo-bar-3.2-1.all.rock', action = 'remove')
    assert msg == "rock version was not found in manifest"
    assert patched_manifest_2 == None
