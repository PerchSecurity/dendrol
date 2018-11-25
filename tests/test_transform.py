from typing import Iterable, Tuple

import pytest
import yaml

from dendrol import Pattern, PatternTree
from dendrol.debug import PatternTreeLoader


TESTS = yaml.load('''

simple-comparison:
  expression: >
    [ipv4-addr:value = '1.2.3.4']

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


joined-comparisons:
  expression: >
    [email-message:subject = 'Yo!' AND email-message:body LIKE '%malicious%']

  pattern:
    observation:
      objects: {email-message}
      join: AND
      qualifiers:
      expressions:
        - comparison:
            object: email-message
            path: [subject]
            negated:
            operator: '='
            value: Yo!
        - comparison:
            object: email-message
            path: [body]
            negated:
            operator: LIKE
            value: '%malicious%'


complex-comparisons:
  expression: >
    [file:name = 'test.exe' AND (file:size < 4 OR file:size > 4096)]

  pattern:
    observation:
      objects: {file}
      join: AND
      qualifiers:
      expressions:
        - comparison:
            object: file
            path: [name]
            negated:
            operator: '='
            value: test.exe
        - expression:
            join: OR
            expressions:
              - comparison:
                  object: file
                  path: [size]
                  negated:
                  operator: '<'
                  value: 4
              - comparison:
                  object: file
                  path: [size]
                  negated:
                  operator: '>'
                  value: 4096


dictionary-object-properties:
  expression: >
    [email-message:from_ref.value MATCHES '.*']

  pattern:
    observation:
      objects: {email-message}
      join:
      qualifiers:
      expressions:
        - comparison:
            object: email-message
            path:
              - from_ref
              - value
            negated:
            operator: MATCHES
            value: .*


list-object-properties:
  expression: >
    [file:extensions.'windows-pebinary-ext'.sections[*].entropy > 7.0]

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


start-stop-qualifier:
  expression: >
    [ipv4-addr:value = '1.2.3.4'] START t'2017-06-29T00:00:00Z' STOP t'2017-12-05T00:00:00Z'

  pattern:
    observation:
      objects: {ipv4-addr}
      join:
      qualifiers:
        - start_stop:
            start: 2017-06-29 00:00:00
            stop: 2017-12-05 00:00:00
      expressions:
        - comparison:
            object: ipv4-addr
            path: [value]
            negated:
            operator: '='
            value: '1.2.3.4'


within-qualifier:
  expression: >
    [ipv4-addr:value = '1.2.3.4'] WITHIN 10 SECONDS

  pattern:
    observation:
      objects: {ipv4-addr}
      join:
      qualifiers:
        - within:
            value: 10
            unit: SECONDS
      expressions:
        - comparison:
            object: ipv4-addr
            path: [value]
            negated:
            operator: '='
            value: '1.2.3.4'


repeated-qualifier:
  expression: >
    [ipv4-addr:value = '1.2.3.4'] REPEATS 5 TIMES

  pattern:
    observation:
      objects: {ipv4-addr}
      join:
      qualifiers:
        - repeats:
            value: 5
      expressions:
        - comparison:
            object: ipv4-addr
            path: [value]
            negated:
            operator: '='
            value: '1.2.3.4'


multiple-qualifiers:
  expression: >
    [ipv4-addr:value = '1.2.3.4'] REPEATS 5 TIMES WITHIN 10 SECONDS

  pattern:
    observation:
      objects: {ipv4-addr}
      join:
      qualifiers:
        - repeats:
            value: 5
        - within:
            value: 10
            unit: SECONDS
      expressions:
        - comparison:
            object: ipv4-addr
            path: [value]
            negated:
            operator: '='
            value: '1.2.3.4'


joined-observation:
  expression: >
    [domain-name:value = 'xyz.com'] AND
    [file:name = 'test.exe']

  pattern:
    expression:
      join: AND
      qualifiers:
      expressions:
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
                  value: xyz.com
        - observation:
            objects: {file}
            join:
            qualifiers:
            expressions:
              - comparison:
                  object: file
                  path: [name]
                  negated:
                  operator: '='
                  value: test.exe


stix2-patterning-example:
  source:
  expression: >
    (
      [ipv4-addr:value = '198.51.100.1/32' OR
       ipv4-addr:value = '203.0.113.33/32' OR
       ipv6-addr:value = '2001:0db8:dead:beef:dead:beef:dead:0001/128']

      FOLLOWEDBY [
        domain-name:value = 'example.com']

    ) WITHIN 600 SECONDS

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

''', Loader=PatternTreeLoader)


def get_tests() -> Iterable[Tuple[str, str, dict]]:
    for name, test in TESTS.items():
        expression = test['expression']

        pattern = test['pattern']
        tree = {'pattern': pattern}
        expected = PatternTree.from_dict(tree)

        yield name, expression, expected


@pytest.mark.parametrize('input,expected', [
    pytest.param(expression, expected, id=name)
    for name, expression, expected in get_tests()
])
def test_dict_tree_visitor(input, expected):
    pattern = Pattern(input)
    dict_tree = pattern.to_dict_tree()

    expected = expected
    actual = dict_tree
    assert expected == actual
