"""Exercise real zipimport resources; this ZIP is a test fixture, not an APWorld build."""
import importlib
from importlib.resources import files
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

from .. import data as data_module


@pytest.fixture
def zipped_resources(tmp_path, monkeypatch):
    package_name = "gk_resource_fixture"
    archive = tmp_path / "resources.zip"
    source = Path(data_module.__file__).parent / "data"
    with ZipFile(archive, "w") as fixture:
        fixture.writestr(f"{package_name}/__init__.py", "")
        for resource in sorted(source.rglob("*.json")):
            fixture.write(resource, f"{package_name}/data/{resource.relative_to(source).as_posix()}")
        fixture.writestr(f"{package_name}/data/broken.json", "{")
        # Deliberately write these out of lexical order.
        for name in ("z.json", "nested/b.json", "a.json", "unused/ignored.json", "readme.txt"):
            fixture.writestr(f"{package_name}/sample/{name}", "{}")
    monkeypatch.syspath_prepend(str(archive))
    package = importlib.import_module(package_name)
    root = files(package)

    def package_files(anchor):
        assert anchor == data_module.__package__
        return root

    monkeypatch.setattr(data_module, "files", package_files)
    yield root
    sys.modules.pop(package_name, None)


def test_zip_items_and_recipes_match_installed_data(zipped_resources):
    items = data_module.load_items()
    recipes = data_module.load_recipes()
    assert items
    assert recipes
    assert list(items.items()) == list(data_module.data.items.items())
    assert list(recipes.items()) == list(data_module.data.recipes.items())


def test_zip_traversal_is_sorted_and_skips_unused(zipped_resources):
    resources = list(data_module.iter_json_files(zipped_resources.joinpath("sample")))
    assert [resource.name for resource in resources] == ["a.json", "b.json", "z.json"]
    assert all(data_module.load_json_data(resource) == {} for resource in resources)
    assert [resource.name for resource in data_module.iter_json_files(
        zipped_resources.joinpath("sample"), recursive=False)] == ["a.json", "z.json"]


def test_zip_json_errors(zipped_resources):
    with pytest.raises(ValueError, match="Failed to parse JSON"):
        data_module.load_json_data("broken.json")
    with pytest.raises(FileNotFoundError):
        data_module.load_json_data("missing.json")
