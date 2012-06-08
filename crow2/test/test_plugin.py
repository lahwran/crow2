"""
Tests for crow2.plugin

Note: these tests load a bunch of modules and just leave them loaded. It should be
okay to leave them loaded because none of them change any state or are referenced
again, but just fyi.
"""
import sys

import pytest

import crow2.plugin
import crow2.test.setup

plugin_targets = "crow2.test.plugin_targets."
cases = [
        ("simple_package", ("child_1", "child_b", "child_z",
            "the_package", "subpackage")),
        ("explicit_children", ("child_1", "child_2", "explicit_children")),
        ("simple_module", ("simple_module",))
]

ids = set(("1", "B", "Z"))

@pytest.mark.parametrize(("packagename", "names"), cases)
def test_loader(packagename, names):
    """
    Test that the loader can load modules
    """
    modulename = plugin_targets + packagename

    instance = crow2.plugin.Tracker(modulename)

    instance.load()

    assert len(instance.plugins) == len(names)
    assert set([plugin.myname for plugin in instance.plugins]) == set(names)

    with pytest.raises(crow2.plugin.AlreadyLoadedError):
        instance.load()

def test_load_errors():
    modulename = plugin_targets + "nonexistant_module"
    instance = crow2.plugin.Tracker(modulename)
    with pytest.raises(crow2.plugin.LoadError):
        instance.load()

    modulename = plugin_targets + "redirect_loop_0"
    instance = crow2.plugin.Tracker(modulename)
    with pytest.raises(crow2.plugin.LoadRedirectError):
        instance.load()

    modulename = plugin_targets + "broken_module"
    instance = crow2.plugin.Tracker(modulename)
    with pytest.raises(crow2.plugin.LoadError):
        instance.load()
    

def create_empty(path):
    """
    Create 
    """
    writer = path.open("w")
    writer.write("")
    writer.close()

def test_listpackage(tmpdir, monkeypatch):
    """
    Test that listpackage is able to accurately detect various kinds of python files
    """
    packagename = "test_listpackage_package"
    packagepath = tmpdir.join(packagename)
    children = set("child" + id for id in ids)

    packagepath.mkdir()
    create_empty(packagepath.join("__init__.py"))
    for child in children:
        create_empty(packagepath.join(child+".py"))

    getmodulename = lambda parent, name: name.partition(".")[0]
    monkeypatch.setattr(crow2.plugin, "getmodulename", getmodulename)
    monkeypatch.syspath_prepend(tmpdir)

    result = crow2.plugin.listpackage([str(packagepath)])

    assert result == children

def test_getmodulename(tmpdir):
    """
    Test that getmodulename can accurately determine a module's python name from
    its filename.
    """
    packagename = "test_getmodulename_package"
    packagepath = tmpdir.join(packagename)
    children = set(("child" + id, suffix) for suffix in crow2.plugin.suffixes
                                  for id in ids)
    subpackages = set(("pkg%d" % num, suffix) for num, suffix in enumerate(crow2.plugin.suffixes))
    emptydirs = set("emptydir" + id for id in ids)

    packagepath.mkdir()
    create_empty(packagepath.join("__init__.py"))
    for name, suffix in children:
        create_empty(packagepath.join(name + suffix))
    for subpackage, suffix in subpackages:
        subpackagepath = packagepath.join(subpackage)
        subpackagepath.mkdir()
        create_empty(subpackagepath.join("__init__"+suffix))
    for emptydir in emptydirs:
        packagepath.join(emptydir).mkdir()

    for name, suffix in children:
        filename = name+suffix
        result = crow2.plugin.getmodulename(str(packagepath), filename)
        assert result == name
    for name, suffix in subpackages:
        result = crow2.plugin.getmodulename(str(packagepath), name)
        assert result == name
    for name in emptydirs:
        result = crow2.plugin.getmodulename(str(packagepath), name)
        assert result == None
