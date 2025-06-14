from html.parser import HTMLParser
from pathlib import Path
import json


class ManifestLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.manifest_href = None

    def handle_starttag(self, tag, attrs):
        if tag == 'link':
            attr_dict = dict(attrs)
            if attr_dict.get('rel') == 'manifest':
                self.manifest_href = attr_dict.get('href')


def test_manifest_linked_in_index():
    parser = ManifestLinkParser()
    index_path = Path(__file__).resolve().parents[1] / 'index.html'
    parser.feed(index_path.read_text())
    assert parser.manifest_href == 'manifest.json'


def test_manifest_fields():
    manifest_path = Path(__file__).resolve().parents[1] / 'manifest.json'
    data = json.loads(manifest_path.read_text())
    assert 'name' in data
    assert 'short_name' in data
