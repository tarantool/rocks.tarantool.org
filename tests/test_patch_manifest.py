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

    msg, manifest = patch_manifest(manifest, 'cartridge-6.6.6-1.src.rock')
    assert msg == "rock entry was successfully added to manifest"
    msg, manifest = patch_manifest(manifest, 'cartridge-6.6.6-1.all.rock')
    assert msg == "rock entry was successfully added to manifest"

    assert manifest == manifest_expected

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
    msg, manifest = patch_manifest(manifest, 'foo-bar-dev-1.rockspec',
        rock_content = rockspec)
    assert msg == "rock entry was successfully added to manifest"

    rockspec = """\
        package = 'foo-bar'
        version = '5.4.3.2-1'
    """
    msg, manifest = patch_manifest(manifest, 'foo-bar-5.4.3.2-1.rockspec',
        rock_content = rockspec)
    assert msg == "rock entry was successfully added to manifest"

    assert manifest == manifest_expected

    with pytest.raises(InvalidUsage) as err:
        patch_manifest(manifest, 'foo-bar-dev-2.rockspec', rock_content = rockspec)
    assert err.value.message == "rockspec name does not match package or version"

    with pytest.raises(InvalidUsage) as err:
        patch_manifest(manifest, 'foo-baz-dev-1.rockspec', rock_content = rockspec)
    assert err.value.message == "rockspec name does not match package or version"


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

def test_remove():
    manifest = dedent("""\
        commands = {}
        modules = {}
        repository = {
            ["foo-bar"] = {
                ["3.2-1"] = {
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

    msg, manifest = patch_manifest(manifest, 'foo-bar-3.2-1.rockspec',
        action = 'remove')
    assert msg == "rock was successfully removed from manifest"

    with pytest.raises(InvalidUsage) as err:
        patch_manifest(manifest, 'foo-bar-dev-1.all.rock', action = 'remove')
    assert err.value.message == "rock architecture was not found in manifest"

    with pytest.raises(InvalidUsage) as err:
        patch_manifest(manifest, 'foo-bar-3.2-1.rockspec', action = 'remove')
    assert err.value.message == "rock version was not found in manifest"

    with pytest.raises(InvalidUsage) as err:
        patch_manifest(manifest, 'foo-baz-dev-1.rockspec', action = 'remove')
    assert err.value.message == "rock was not found in manifest"

    with pytest.raises(InvalidUsage) as err:
        patch_manifest(manifest, 'foo.rockspec', action = 'remove')
    assert err.value.message == "filename parsing error"

    assert manifest == manifest_expected
