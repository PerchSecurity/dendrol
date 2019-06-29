import re
from typing import Tuple, Iterable

import pytest
from ww import f

from dendrol import PatternTree, load_tree


# NOTE: whitespace is important here!
#       these structures will be compared char-by-char, so mind trailing spaces.
TESTS = '''

name: simple
pattern:
  observation:
    objects: {ipv4-addr}
    join:
    qualifiers:
    expressions:
      - comparison:
          object: ipv4-addr
          path: [value]
          negated:
          operator: '='
          value: 1.2.3.4

---

name: multiple-object-types
pattern:
  expression:
    join: FOLLOWEDBY
    qualifiers:
      - within:
          value: 600
          unit: SECONDS
    expressions:
      - observation:
          objects:
            ? ipv4-addr
            ? ipv6-addr
          join: OR
          qualifiers:
          expressions:
            - comparison:
                object: ipv4-addr
                path: [value]
                negated:
                operator: '='
                value: 198.51.100.1/32
            - comparison:
                object: ipv4-addr
                path: [value]
                negated:
                operator: '='
                value: 203.0.113.33/32
            - comparison:
                object: ipv6-addr
                path: [value]
                negated:
                operator: '='
                value: 2001:0db8:dead:beef:dead:beef:dead:0001/128
      - observation:
          objects: {domain-name}
          join:
          qualifiers:
          expressions:
            - comparison:
                object: domain-name
                path: [value]
                negated:
                operator: '='
                value: example.com

---

name: list-path-explicit
pattern:
  observation:
    objects: {file}
    join:
    qualifiers:
    expressions:
      - comparison:
          object: file
          path:
            - extensions
            - windows-pebinary-ext
            - sections
            - [12]
            - entropy
          negated:
          operator: '>'
          value: 7.0

---

name: list-path-any
pattern:
  observation:
    objects: {file}
    join:
    qualifiers:
    expressions:
      - comparison:
          object: file
          path:
            - extensions
            - windows-pebinary-ext
            - sections
            - [*]
            - entropy
          negated:
          operator: '>'
          value: 7.0

'''


RGX_TEST_NAME = re.compile(r'^name: (\S+)\s+', re.MULTILINE)


def get_tests() -> Iterable[Tuple[str, str, PatternTree]]:
    docs = TESTS.split('\n---\n')
    for i, doc in enumerate(docs):
        doc = doc.strip()

        name_match = RGX_TEST_NAME.match(doc)
        if name_match:
            name = name_match.group(1)
            doc = RGX_TEST_NAME.sub('', doc)
        else:
            name = f('doc {i}')

        tree = load_tree(doc)
        yield name, doc, tree


@pytest.mark.parametrize('source,tree', [
    pytest.param(source, tree, id=name)
    for name, source, tree in get_tests()
])
def test_yaml_repr(source: str, tree: PatternTree):
    expected = source
    actual = tree.serialize().strip()
    assert expected == actual
