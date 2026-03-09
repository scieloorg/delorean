# coding: utf-8
import codecs
import copy
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pyramid import testing


HERE = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def pyramid_test_config():
    testing.setUp()
    try:
        yield
    finally:
        testing.tearDown()


def _load_json(relative_path):
    with open(HERE / relative_path, encoding="utf-8") as f:
        return json.load(f)


def _load_iso_lines(relative_path):
    with codecs.open(str(HERE / relative_path), "r", "iso8859-1") as f:
        return f.readlines()


class EndpointResource:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def _next_response(self):
        if isinstance(self._response, list):
            if not self._response:
                raise AssertionError("No mocked response left")
            value = self._response.pop(0)
        else:
            value = self._response
        return copy.deepcopy(value)

    def get(self, **kwargs):
        self.calls.append(kwargs)
        return self._next_response()


class EndpointCollection(EndpointResource):
    def __init__(self, list_response, item_response=None, item_responses=None):
        super(EndpointCollection, self).__init__(list_response)
        self.item_response = item_response
        self.item_responses = item_responses or {}
        self.item_calls = []

    def __call__(self, resource_id):
        response = self.item_responses.get(str(resource_id), self.item_response)
        if response is None:
            raise AssertionError("No mocked item response for %s" % resource_id)
        endpoint = EndpointResource(response)
        original_get = endpoint.get

        def wrapped_get(**kwargs):
            self.item_calls.append((str(resource_id), kwargs))
            return original_get(**kwargs)

        endpoint.get = wrapped_get
        return endpoint


class FakeAPI:
    def __init__(self, endpoints):
        for name, endpoint in endpoints.items():
            setattr(self, name, endpoint)


def _make_slumber_lib(endpoints):
    return SimpleNamespace(API=lambda _url: FakeAPI(endpoints))


def _assert_issue_record(record, expected):
    for field, value in expected.items():
        if field not in ("journal", "sections", "display"):
            assert value == record[field]

        if field == "journal":
            for jfield, jvalue in value.items():
                assert jvalue == record["journal"][jfield]

        if field == "sections":
            for sfield, svalue in value.items():
                for idx, title in enumerate(svalue):
                    assert sorted(title) == sorted(record["sections"][sfield][idx])

        if field == "display":
            for dfield, dvalue in value.items():
                assert dvalue == record["display"][dfield]


# Functional tests

def test_app_status():
    from .views import app_status

    request = testing.DummyRequest()
    info = app_status(request)
    assert info["app_name"] == "delorean"


# Unit tests

def test_generate_filename():
    from delorean.domain import DeLorean

    dummy_datetime = Mock()
    dummy_datetime.now.return_value = object()
    dummy_datetime.strftime.return_value = "20120712-10:07:34:803942"

    dl = DeLorean("http://localhost:8000/api/v1/", datetime_lib=dummy_datetime)

    assert dl._generate_filename("title") == "title-20120712-10:07:34:803942.tar"


def test_generate_title_bundle(tmp_path):
    from delorean.domain import DeLorean

    dummy_datetime = Mock()
    dummy_datetime.now.return_value = object()
    dummy_datetime.strftime.return_value = "20120712-10:07:34:803942"

    collector_return = [{"title": "Revista"}]
    dummy_titlecollector = Mock(return_value=collector_return)

    transformer_instance = Mock()
    transformer_instance.transform_list.return_value = "!ID 0\n"
    dummy_transformer = Mock(return_value=transformer_instance)

    dl = DeLorean(
        "http://localhost:8000/api/v1/",
        datetime_lib=dummy_datetime,
        titlecollector=dummy_titlecollector,
        transformer=dummy_transformer,
    )

    bundle_url = dl.generate_title(target=str(tmp_path), collection="brasil")

    assert bundle_url == "title-20120712-10:07:34:803942.tar"
    dummy_titlecollector.assert_called_once_with(
        "http://localhost:8000/api/v1/",
        collection="brasil",
        username=None,
        api_key=None,
    )
    assert dummy_transformer.call_count == 1
    transformer_instance.transform_list.assert_called_once_with(collector_return)
    assert (tmp_path / bundle_url).exists()


def test_datacollector_instantiation_abstract_error():
    from delorean.domain import DataCollector

    with pytest.raises(TypeError):
        DataCollector("https://manager.scielo.org/api/v1/journal/brasil/0102-6720")


def test_datacollector_fetch_all_data():
    from delorean.domain import DataCollector

    valid_full_microset = {
        "objects": [
            {"title": "ABCD. Arquivos Brasileiros de Cirurgia Digestiva (São Paulo)"},
        ],
        "meta": {"next": None},
    }

    class ConcreteDataCollector(DataCollector):
        _resource_name = "journals"

        def get_data(self, data):
            return data

    journals = EndpointCollection(list_response=valid_full_microset)
    slumber_lib = _make_slumber_lib({"journals": journals})

    dc = ConcreteDataCollector(
        "https://manager.scielo.org/api/v1/journal/brasil/0102-6720", slumber_lib=slumber_lib
    )

    res = dc.fetch_data(0, 50)
    assert isinstance(res, dict)
    assert "objects" in res
    assert len(res["objects"]) == 1


def test_datacollector_fetch_data_from_collection():
    from delorean.domain import DataCollector

    valid_full_microset = {
        "objects": [
            {"title": "ABCD. Arquivos Brasileiros de Cirurgia Digestiva (São Paulo)"},
        ],
        "meta": {"next": None},
    }

    class ConcreteDataCollector(DataCollector):
        _resource_name = "journals"

        def get_data(self, data):
            return data

    journals = EndpointCollection(list_response=valid_full_microset)
    slumber_lib = _make_slumber_lib({"journals": journals})

    dc = ConcreteDataCollector(
        "https://manager.scielo.org/api/v1/journal/brasil/0102-6720",
        slumber_lib=slumber_lib,
        collection="brasil",
    )

    res = dc.fetch_data(0, 50, collection="brasil")
    assert isinstance(res, dict)
    assert "objects" in res
    assert len(res["objects"]) == 1
    assert journals.calls[-1] == {"offset": 0, "limit": 50, "collection": "brasil"}


def test_titlecollector_instantiation():
    from delorean.domain import TitleCollector

    journals = EndpointCollection(list_response={"objects": [], "meta": {"next": None}})
    dc = TitleCollector(
        "https://manager.scielo.org/api/v1/",
        slumber_lib=_make_slumber_lib({"journals": journals}),
        collection="brasil",
    )
    assert isinstance(dc, TitleCollector)


def test_titlecollector_gen_iterable():
    from delorean.domain import TitleCollector

    journals = EndpointCollection(list_response={"objects": [], "meta": {"next": None}})
    dc = TitleCollector(
        "https://manager.scielo.org/api/v1/", slumber_lib=_make_slumber_lib({"journals": journals})
    )
    it = iter(dc)
    assert hasattr(it, "__next__")


def test_titlecollector_get_data():
    from delorean.domain import TitleCollector

    journal_data = {"meta": {"next": None}, "objects": [_load_json("tests_assets/journal_meta_beforeproc.json")]}

    journals = EndpointCollection(
        list_response=journal_data,
        item_response={"title": "Previous title"},
    )
    users = EndpointCollection(list_response={"objects": [], "meta": {"next": None}}, item_response={"username": "albert.einstein@scielo.org"})
    sponsors = EndpointCollection(
        list_response={"objects": [], "meta": {"next": None}},
        item_response={"name": "Colégio Brasileiro de Cirurgia Digestiva - CBCD"},
    )

    dc = TitleCollector(
        "https://manager.scielo.org/api/v1/",
        slumber_lib=_make_slumber_lib(
            {
                "journals": journals,
                "users": users,
                "sponsors": sponsors,
            }
        ),
    )

    desired = _load_json("tests_assets/journal_meta_afterproc.json")
    records = list(dc)

    assert len(records) == 1
    for field, value in records[0].items():
        assert value == desired[field]


def test_sectioncollector_instantiation():
    from delorean.domain import SectionCollector

    journals = EndpointCollection(list_response={"objects": [], "meta": {"next": None}})
    dc = SectionCollector(
        "https://manager.scielo.org/api/v1/", slumber_lib=_make_slumber_lib({"journals": journals})
    )
    assert isinstance(dc, SectionCollector)


def test_sectioncollector_gen_iterable():
    from delorean.domain import SectionCollector

    journals = EndpointCollection(list_response={"objects": [], "meta": {"next": None}})
    dc = SectionCollector(
        "https://manager.scielo.org/api/v1/", slumber_lib=_make_slumber_lib({"journals": journals})
    )
    it = iter(dc)
    assert hasattr(it, "__next__")


def test_sectioncollector_get_data():
    from delorean.domain import SectionCollector

    journal_data = {"meta": {"next": None}, "objects": [_load_json("tests_assets/section_meta_beforeproc.json")]}

    section_data = {
        "code": "ABCD030",
        "titles": [["pt", "Artigos de Revisão"], ["en", "Review Articles"]],
        "id": "5676",
    }

    journals = EndpointCollection(list_response=journal_data)
    sections = EndpointCollection(
        list_response={"objects": [], "meta": {"next": None}},
        item_response=section_data,
    )

    dc = SectionCollector(
        "https://manager.scielo.org/api/v1/",
        slumber_lib=_make_slumber_lib({"journals": journals, "sections": sections}),
    )

    desired = _load_json("tests_assets/section_meta_afterproc.json")
    records = list(dc)

    assert len(records) == 1
    for field, value in desired.items():
        if field == "sections":
            assert records[0]["sections"][0] in value


def test_issuecollector_instantiation():
    from delorean.domain import IssueCollector

    issues = EndpointCollection(list_response={"objects": [], "meta": {"next": None}})
    dc = IssueCollector("https://manager.scielo.org/api/v1/", slumber_lib=_make_slumber_lib({"issues": issues}))
    assert isinstance(dc, IssueCollector)


def test_issuecollector_gen_iterable():
    from delorean.domain import IssueCollector

    issues = EndpointCollection(list_response={"objects": [], "meta": {"next": None}})
    dc = IssueCollector("https://manager.scielo.org/api/v1/", slumber_lib=_make_slumber_lib({"issues": issues}))
    it = iter(dc)
    assert hasattr(it, "__next__")


def _run_issue_collector_case(beforeproc_file, expected_file):
    from delorean.domain import IssueCollector

    issue_data = {"meta": {"next": None}, "objects": [_load_json(beforeproc_file)]}

    journal_data = {
        "title": "ABCD. Arquivos Brasileiros de Cirurgia Digestiva (São Paulo)",
        "short_title": "ABCD, arq. bras. cir. dig.",
        "eletronic_issn": "",
        "print_issn": "0102-6720",
        "scielo_issn": "print",
        "publisher_name": "Colégio Brasileiro de Cirurgia Digestiva",
        "publication_city": "São Paulo",
        "sponsors": ["Brazilian Archives of Digestive Surgery"],
        "resource_uri": "/api/v1/journals/2647/",
        "acronym": "ABCD",
        "title_iso": "ABCD, arq. bras. cir. dig",
        "medline_title": "ABCD arq bras cir dig",
        "use_license": {
            "disclaimer": "Licencia Creative Commons",
            "id": "1",
            "license_code": "BY-NC",
            "reference_url": None,
            "resource_uri": "/api/v1/uselicenses/1/",
        },
    }

    section_data = {
        "resource_uri": "/api/v1/sections/67221/",
        "titles": [["pt", "Técnica"], ["en", "Technic"]],
        "code": "CBCD-f28r",
    }

    issues = EndpointCollection(list_response=issue_data)
    journals = EndpointCollection(
        list_response={"objects": [], "meta": {"next": None}},
        item_response=journal_data,
    )
    sections = EndpointCollection(
        list_response={"objects": [], "meta": {"next": None}},
        item_response=section_data,
    )

    dc = IssueCollector(
        "https://manager.scielo.org/api/v1/",
        slumber_lib=_make_slumber_lib(
            {
                "issues": issues,
                "journals": journals,
                "sections": sections,
            }
        ),
    )

    desired = _load_json(expected_file)
    records = list(dc)
    assert len(records) == 1
    _assert_issue_record(records[0], desired)


def test_issuecollector_get_data():
    _run_issue_collector_case("tests_assets/issue_meta_beforeproc.json", "tests_assets/issue_meta_afterproc.json")


def test_issuecollector_get_data_pub_monthly():
    _run_issue_collector_case(
        "tests_assets/issue_meta_beforeproc_pub_monthly.json",
        "tests_assets/issue_meta_afterproc_pub_monthly.json",
    )


def test_issuecollector_get_data_special():
    _run_issue_collector_case("tests_assets/issue_spe_meta_beforeproc.json", "tests_assets/issue_spe_meta_afterproc.json")


class TestTransformer:
    tpl_basic = "Pra frente, ${country}"
    tpl_basic_id = "!ID ${i}\n!v100!${title}"
    tpl_basic_compound = (
        """
    !ID 0
    !v100!${title}
    % for l in languages:
    !v350!${l['iso_code']}
    % endfor
    """.strip()
    )

    def _make_one(self, *args, **kwargs):
        from delorean.domain import Transformer

        return Transformer(*args, **kwargs)

    def test_instantiation(self):
        from delorean.domain import Transformer

        t = self._make_one(self.tpl_basic)
        assert isinstance(t, Transformer)

    def test_basic_transformation(self):
        t = self._make_one(self.tpl_basic)
        result = t.transform({"country": "Brasil"})
        assert result == "Pra frente, Brasil"

    def test_transformation_missing_data(self):
        t = self._make_one(self.tpl_basic)
        with pytest.raises(ValueError):
            t.transform({})

    def test_transformation_wrong_typed_data(self):
        t = self._make_one(self.tpl_basic)
        for typ in [[], 1, (), "str", set()]:
            with pytest.raises(TypeError):
                t.transform(typ)

    def test_basic_list_transformation(self):
        t = self._make_one(self.tpl_basic)
        data_list = [{"country": "Brasil"}, {"country": "Egito"}]
        result = t.transform_list(data_list)
        assert result == "Pra frente, Brasil\nPra frente, Egito"

    def test_transformation_missing_data_list(self):
        t = self._make_one(self.tpl_basic)
        with pytest.raises(ValueError):
            t.transform_list([{"country": "Brasil"}, {}])

    def test_transformation_wrong_typed_data_list(self):
        t = self._make_one(self.tpl_basic)
        for typ in [1, "str", {}, set()]:
            with pytest.raises(TypeError):
                t.transform_list(typ)

    def test_transformation_iterable_data(self):
        t = self._make_one(self.tpl_basic)

        def item_factory():
            for i in range(2):
                yield {"country": "Brasil%s" % i}

        result = t.transform_list(item_factory())
        assert result == "Pra frente, Brasil0\nPra frente, Brasil1"

    def test_transformation_with_callable(self):
        t = self._make_one(self.tpl_basic_id)

        def add_index(data_list):
            for i, item in enumerate(data_list):
                item.update({"i": i})

        result = t.transform_list(
            [{"title": "Revista Brasileira"}, {"title": "Revista Mexicana"}],
            add_index,
        )
        assert [part.strip() for part in result.split("\n")] == (
            "!ID 0\n!v100!Revista Brasileira\n!ID 1\n!v100!Revista Mexicana".split("\n")
        )

    def test_compound_transformation(self):
        t = self._make_one(self.tpl_basic_compound)
        d = {
            "title": "ABCD. Arquivos Brasileiros",
            "languages": [{"iso_code": "en"}, {"iso_code": "pt"}],
        }
        result = t.transform(d)
        assert [part.strip() for part in result.split("\n")] == (
            "!ID 0\n!v100!ABCD. Arquivos Brasileiros\n!v350!en\n!v350!pt\n".split("\n")
        )

    def test_compound_transformation_filebased(self):
        t = self._make_one(filename=str(HERE / "tests_assets/basic_compound.txt"))
        d = {
            "title": "ABCD. Arquivos Brasileiros",
            "languages": [{"iso_code": "en"}, {"iso_code": "pt"}],
        }
        result = t.transform(d)
        assert [part.strip() for part in result.split("\n")] == (
            "!ID 0\n!v100!ABCD. Arquivos Brasileiros\n!v350!en\n!v350!pt\n".split("\n")
        )

    def test_title_db_generation(self):
        t = self._make_one(filename=str(HERE / "templates/title_db_entry.txt"))
        d = _load_json("tests_assets/journal_meta_afterproc.json")
        generated_id = t.transform(d).splitlines()
        canonical_id = _load_iso_lines("tests_assets/journal_meta.id")

        del generated_id[0]

        for i in range(len(generated_id)):
            assert generated_id[i].strip() == canonical_id[i].strip()

        assert len(generated_id) == len(canonical_id)

    def test_title_db_generation_with_no_public_status(self):
        t = self._make_one(filename=str(HERE / "templates/title_db_entry.txt"))
        d = _load_json("tests_assets/journal_meta_afterproc.json")
        d["pub_status"] = "inprogress"
        generated_id = t.transform(d).splitlines()
        canonical_id = _load_iso_lines("tests_assets/journal_meta_notpublic.id")

        del generated_id[0]

        for i in range(len(generated_id)):
            assert generated_id[i].strip() == canonical_id[i].strip()

        assert len(generated_id) == len(canonical_id)

    def test_issue_db_generation(self):
        t = self._make_one(filename=str(HERE / "templates/issue_db_entry.txt"))
        d = _load_json("tests_assets/issue_meta_afterproc.json")
        generated_id = t.transform(d).splitlines()
        canonical_id = _load_iso_lines("tests_assets/issue_meta.id")

        del generated_id[0]

        for i in range(len(canonical_id)):
            assert generated_id[i].strip() == canonical_id[i].strip()

        assert len(generated_id) == len(canonical_id)

    def test_issue_db_generation_special(self):
        t = self._make_one(filename=str(HERE / "templates/issue_db_entry.txt"))
        d = _load_json("tests_assets/issue_spe_meta_afterproc.json")
        generated_id = t.transform(d).splitlines()
        canonical_id = _load_iso_lines("tests_assets/issue_spe_meta.id")

        del generated_id[0]

        for i in range(len(canonical_id)):
            assert generated_id[i].strip() == canonical_id[i].strip()

        assert len(generated_id) == len(canonical_id)

    def test_section_db_generation(self):
        t = self._make_one(filename=str(HERE / "templates/section_db_entry.txt"))
        d = _load_json("tests_assets/section_meta_afterproc.json")
        generated_id = t.transform(d).splitlines()
        canonical_id = _load_iso_lines("tests_assets/section_meta.id")

        del generated_id[0]

        for i in range(len(canonical_id)):
            assert generated_id[i].strip() == canonical_id[i].strip()

        assert len(generated_id) == len(canonical_id)


class TestBundle:
    basic_data = [("arq_a", "Arq A content"), ("arq_b", "Arq B content")]

    def _make_one(self, *args, **kwargs):
        from delorean.domain import Bundle

        return Bundle(*args, **kwargs)

    def test_instantiation(self):
        from delorean.domain import Bundle

        p = self._make_one(*self.basic_data)
        assert isinstance(p, Bundle)

    def test_generate_tarball(self):
        data_as_dict = dict(self.basic_data)
        p = self._make_one(*self.basic_data)
        tar_handler = p._tar()
        assert hasattr(tar_handler, "read")
        assert hasattr(tar_handler, "name")

        t = tarfile.open(tar_handler.name, "r")
        for member in t.getmembers():
            assert member.name in data_as_dict

    def test_deploy_data(self, tmp_path):
        p = self._make_one(*self.basic_data)
        p.deploy(str(tmp_path / "files" / "zippedfile.tar"))


class TestResourceUnavailableError:
    def test_raise(self):
        from delorean.domain import ResourceUnavailableError

        assert issubclass(ResourceUnavailableError, BaseException)
