<h1 align="center">
  <!-- a bug prevents PyPI from aligning header tags: https://github.com/pypa/readme_renderer/issues/126 -->
  <p align="center">
    <img alt="dendrol" src="https://user-images.githubusercontent.com/33840/49189283-aadc8980-f33b-11e8-9505-77f074448474.png">
  </p>
</h1>
<p align="center">
  <a href="https://pypi.python.org/pypi/dendrol/">
    <img alt="dendrol PyPI version" src="https://camo.githubusercontent.com/be46feea7129311b3dafeef4ac272061f21293de/68747470733a2f2f62616467652e667572792e696f2f70792f64656e64726f6c2e737667">
  </a> 
  <a href="https://pypi.python.org/pypi/dendrol/">
    <img alt="PyPI pyversions" src="https://camo.githubusercontent.com/9b638ffc22ef0b3bd395012d65984ed2c6e1de8e/68747470733a2f2f696d672e736869656c64732e696f2f707970692f707976657273696f6e732f64656e64726f6c2e737667">
  </a>
  <a href="https://pypi.python.org/pypi/dendrol/">
    <img alt="PyPI license" src="https://camo.githubusercontent.com/7ec6b5aecd3c32e4f25d596c8045bf5ffbe7a9af/68747470733a2f2f696d672e736869656c64732e696f2f707970692f6c2f64656e64726f6c2e737667">
  </a>
</p>

<p align="center">
  <b>dendrol</b> parses STIX2 pattern expressions into basic Python structures
</p>

<p align="center">
  <a href="http://docs.oasis-open.org/cti/stix/v2.0/cs01/part5-stix-patterning/stix-v2.0-cs01-part5-stix-patterning.html#_t7hu3hrkvmff">
    <img alt="Iconic STIX2 Pattern visualization" src="https://user-images.githubusercontent.com/33840/47131128-027ed400-d26b-11e8-950b-4c494c9cf4c5.png">
  </a>
</p>

This iconic [STIX2 Pattern](http://docs.oasis-open.org/cti/stix/v2.0/cs01/part5-stix-patterning/stix-v2.0-cs01-part5-stix-patterning.html#_t7hu3hrkvmff) visualization is based upon this example expression:
```
(
  [ipv4-addr:value = '198.51.100.1/32' OR
   ipv4-addr:value = '203.0.113.33/32' OR
   ipv6-addr:value = '2001:0db8:dead:beef:dead:beef:dead:0001/128']

  FOLLOWEDBY [
    domain-name:value = 'example.com']

) WITHIN 600 SECONDS
```

Using the formal STIX2 Pattern grammar, that expression is converted into this parse tree:

![example expression parse tree](https://user-images.githubusercontent.com/33840/47131306-eaf41b00-d26b-11e8-83ab-82a6932b95cf.png)

dendrol will convert that expression (by way of that parse tree) into this more human-readable and machine-actionable form:
```yaml
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
```


# How do I use it?

dendrol provides an interface for parsing STIX2 Pattern Expressions much like [cti-pattern-validator](https://github.com/oasis-open/cti-pattern-validator), with the `dendrol.Pattern` class. This class has a method, `to_dict_tree()`, which converts the ANTLR parse tree to a dict-based tree structure, PatternTree.

```py
from dendrol import Pattern

pattern = Pattern("[domain-name:value = 'http://xyz.com/download']")

assert pattern.to_dict_tree() == {
    'pattern': {
        'observation': {
            'objects': {'domain-name'},
            'join': None,
            'qualifiers': None,
            'expressions': [
                {'comparison': {
                    'object': 'domain-name',
                    'path': ['value'],
                    'negated': None,
                    'operator': '=',
                    'value': 'http://xyz.com/download',
                }}
            ]
        }
    }
}
```

A specialized YAML representation is also proposed, to make visualization of this data a little less cumbersome:

```py
from dendrol import Pattern

pattern = Pattern("[domain-name:value = 'http://xyz.com/download']")

assert str(pattern.to_dict_tree()) == '''\
pattern:
  observation:
    objects: {domain-name}
    join:
    qualifiers:
    expressions:
      - comparison:
          object: domain-name
          path: [value]
          negated:
          operator: '='
          value: http://xyz.com/download
'''
```

For more info, read [The Spec](#the-spec) below, or check out the tests.


# Development
To develop dendrol and run its tests, first clone the repo. Then install the dev and testing dependencies:
```bash
pip install .[dev] .[test]
```

pytest is used for testing:
```bash
py.test
```

Reported issues and pull requests welcomed! From new features and suggestions to typo fixes and poor naming choices, fresh eyes bolster software eternally in development.

If submitting a pull request, please add yourself to the CONTRIBUTORS file for a piece of that sweet, sweet street cred!


# <a name="the-spec" href="#the-spec">The Spec</a>
## Brief
A PatternTree begins with a `'pattern'` key. Below it is an observation expression, with an `'observation'` or `'expression'` key (which may contain more observation expressions joined by AND/OR/FOLLOWEDBY). Below `'observation'` keys are comparison expressions, marked by a `'comparison'` or `'expression'` key (which may contain more comparison expressions joined by AND/OR). `'comparison'` keys denote a single comparison between an object property and a literal value.

## <a name="spec-pattern" href="#spec-pattern">Pattern</a>
```py
{'pattern': {...}}
```
```yaml
pattern:
  ...
```
A PatternTree is a dict with one top-level key, `'pattern'`. This paradigm of a dict with a single key identifying its contents is seen throughout this spec.

The value of this `'pattern'` key is an [observation expression](#spec-observation-expressions).


## <a name="spec-observation-expressions" href="#spec-observation-expressions">Observation Expressions</a>

An Observation Expression is a dict with a single key of either `'expression'` or `'observation'`. An [`'expression'`](#spec-observation-expressions-expression) SHALL contain two or more observation expressions joined by AND/OR/FOLLOWEDBY, whereas an [`'observation'`](#spec-observation-expressions-observation) SHALL contain only comparison expressions.


### <a name="spec-observation-expressions-expression" href="#spec-observation-expressions-expression">Expression</a>
```py
{'expression': {
    'join': oneOf('AND', 'OR', 'FOLLOWEDBY'),
    'qualifiers': [...],
    'expressions': [...],
}}
```
```yaml
expression:
  join: AND | OR | FOLLOWEDBY
  qualifiers:
  expressions:
    - a
    - b
    - ...
```
An `'expression'` is a container for other observation expressions, joined by an observation operator in `'join'`. It MAY have a list of qualifiers in the `'qualifiers'` key, or `None` if there are none.

Its children are in `'expressions'`, whose values SHALL be dicts with single keys (of either `'observation'` or `'expression'`).


### <a name="spec-observation-expressions-observation" href="#spec-observation-expressions-observation">Observation</a>
```py
{'observation': {
    'objects': {'ipv4-addr', 'ipv6-addr', ...},
    'join': oneOf('AND', 'OR'),
    'qualifiers': [...],
    'expressions': [...],
}}
```
```yaml
observation:
  objects:
    ? ipv4-addr
    ? ipv6-addr
    ? ...
  join: AND | OR
  qualifiers:
  expressions:
    - a
    - ...
```
An `'observation'` is analogous to square brackets in STIX2 Pattern Expressions, e.g.: `[ipv4-addr:value = '1.2.3.4']`. Children of an observation (in the `'expressions'` key) SHALL only be comparisons or comparison expressions.

An `'observation'` MAY have qualifiers, but its children MUST NOT.

An `'observation'` MAY have a join method, which denotes how its child [comparison expressions](#spec-comparison-expressions) are to be joined. This method MAY be AND or OR, but MUST NOT be FOLLOWEDBY, because the join method applies to comparison expressions, not observation expressions. If there is only a single child comparison expression, `'join'` MAY be `None`.

An `'observation'` SHALL contain a set of all the object types of its child comparison expressions. This is mainly for human consumption. A STIX2 observation is allowed to contain comparisons on disparate object types, provided they're joined by OR— this is why `'objects'` is a set, not a single string.

If `'objects'` contains only a single object type, it MAY be compacted into set literal form:
```yaml
observation:
  objects: {ipv4-addr}
  join: AND | OR
  qualifiers:
  expressions:
    - a
    - ...
```


### <a name="spec-observation-expressions-qualifiers" href="#spec-observation-expressions-qualifiers">Qualifiers</a>
A Qualifier is a dict having a single key identifying its Qualifier type. Currently, this SHALL be one of:
 - [`'start_stop'`](#spec-observation-expressions-qualifiers-start-stop)
 - [`'within'`](#spec-observation-expressions-qualifiers-within)
 - [`'repeats'`](#spec-observation-expressions-qualifiers-repeats)


#### <a name="spec-observation-expressions-qualifiers-start-stop" href="#spec-observation-expressions-qualifiers-start-stop">Start/Stop Qualifier</a>
```py
{'start_stop': {
    'start': datetime(2018, 10, 7, 0, 0, tzinfo=tzutc()),
    'stop': datetime(2018, 10, 7, 23, 59, tzinfo=tzutc()),
}}
```
```yaml
start_stop:
  start: 2018-10-07T00:00:00Z
  stop: 2018-10-08T23:59:00Z
```
The `'start_stop'` qualifier constrains the timeframe in which its associated observation expressions MUST occur within to evaluate true. Unlike `WITHIN`, `START ... STOP ...` denotes absolute points in time, using datetime literals.

Example STIX2 expression:
```
[a:b = 12] START t'2018-10-07T00:00:00Z' STOP t'2018-10-08T23:59:00Z'
```
In STIX2 Pattern Expressions, all datetimes MUST be in [RFC3339](https://tools.ietf.org/html/rfc3339) format, and MUST be in UTC timezone. datetime literals resemble Python strings with `t` as their modifying char (like an f-string, or a bytestring). Because they must be in UTC timezone, datetime literals MUST end with the `Z` char.

When parsed into Python, they SHALL have a `tzinfo` object with a `dstoffset` of 0.


#### <a name="spec-observation-expressions-qualifiers-within" href="#spec-observation-expressions-qualifiers-within">Within Qualifier</a>
```py
{'within': {
    'value': 600,
    'unit': 'SECONDS',
}}
```
```yaml
within:
  value: 600
  unit: SECONDS
```
The `'within'` qualifier constrains the timeframe in which its associated observation expressions MUST occur within to evaluate true. Unlike `START ... STOP ...`, `WITHIN` denotes relative timeframes, where the latest observation expression MUST occur within the specified number of seconds from the earliest observation expression.

Example STIX2 expression:
```
[a:b = 12] WITHIN 600 SECONDS
```

`SECONDS` is hard-coded into the STIX2 Pattern Expression grammar, and MUST be included in pattern expressions. However, to avoid ambiguity for the reader, and to allow for future STIX2 spec changes, the unit is also included in the Pattern Tree.


#### <a name="spec-observation-expressions-qualifiers-repeats" href="#spec-observation-expressions-qualifiers-repeats">Repeated Qualifier</a>
```py
{'repeats': {
    'value': 9000,
}}
```
```yaml
repeats:
  value: 9000
```
The `'repeats'` qualifier REQUIRES that its associated observation expressions evaluate true at different occasions, for a specified number of times.

Example STIX2 expression:
```
[a:b = 12] REPEATS 9000 TIMES
```

`TIMES` is hard-coded into the STIX2 Pattern Expression grammar, and MUST be included in pattern expressions. However, since there aren't any other obvious units of multiplicity, other than "X times", it has been omitted from the Pattern Tree output — unlike `SECONDS` of `WITHIN`.


## <a name="spec-comparison-expressions" href="#spec-comparison-expressions">Comparison Expressions</a>
A Comparison Expression is a dict with a single key of either `'expression'` or `'comparison'`. An [`'expression'`](#spec-comparison-expressions-expression) SHALL contain two or more comparison expressions joined by AND/OR, whereas a [`'comparison'`](#spec-comparison-expressions-comparison) contains no children, and only marks a comparison of one variable to one literal value.


### <a name="spec-comparison-expressions-expression" href="#spec-comparison-expressions-expression">Expression</a>
```py
{'expression': {
    'join': oneOf('AND', 'OR'),
    'expressions': [a, b, ...],
}}
```
```yaml
expression:
  join: AND | OR
  expressions:
    - a
    - b
    - ...
```
An `'expression'` is a container for other comparison expressions, joined by either AND or OR in `'join'` — comparison expressions do not have FOLLOWEDBY, as they are intended to reference a single object at a single point in time.

An `'expression'` MUST NOT have qualifiers.

Its children are in `'expressions'`, whose values SHALL be dicts with single keys (of either `'comparison'` or `'expression'`).


### <a name="spec-comparison-expressions-comparison" href="#spec-comparison-expressions-comparison">Comparison</a>
```py
{'comparison': {
    'object': 'email-message',
    'path': ['from_ref', 'value'],
    'negated': None,
    'operator': 'MATCHES',
    'value': '.+@malicio\\.us',
}}
```
```yaml
comparison:
  object: email-message
  path:
    - from_ref
    - value
  negated:
  operator: MATCHES
  value: .+@malicio\.us
```
A `'comparison'` represents a single comparison between a STIX2 object property and a literal value. A single string object type SHALL be placed in the `'object'` key.

`'path'` SHALL be a list beginning with a top-level property of the object type denoted in `'object'`, as a string. Following this MAY be any number of child properties, as strings, or list index components/dereferences, denoted as Python `slice()` objects, where `[1]` is equivalent to `slice(start=None, stop=1, step=None)`. The special _match any_ list index from STIX2 (e.g. `file:sections[*]`) is equivalent to `slice(start=None, stop='*', step=None)`.

`'negated'` SHALL be a bool denoting whether the operator SHALL be negated during evaluation. STIX2 allows a `NOT` keyword before the operator: `file:name NOT MATCHES 'james.*'`. If the operator is not negated, `'negated'` MAY be `None`. (This allows for a more compact YAML representation — where the value may simply be omitted.)

`'operator'` SHALL be a string representing the operator, e.g. `'>'`, `'LIKE'`, or `'='`.

`'value'` MAY be any static Python value. Currently, only strings, bools, ints, floats, datetimes, and bytes are outputted, but this could change in the future (e.g. if compiled regular expressions are deemed useful).

If `'path'` contains only a single property, it MAY be compacted into list literal form:
```yaml
comparison:
  object: domain-name
  path: [value]
  negated:
  operator: =
  value: cnn.com
```
