from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime
from typing import Union, Any

import yaml

from .transform import CompactibleObject, PatternTree


DEFAULT_SET_TAG = 'tag:yaml.org,2002:set'
DEFAULT_SLICE_TAG = '!slice'


def load_tree(s: str) -> PatternTree:
    d = yaml.load(s, Loader=PatternTreeLoader)
    return PatternTree.from_dict(d)


def dump_tree(tree: Union[Any, PatternTree]) -> str:
    return yaml.dump(
        tree,
        Dumper=PatternTreeDumper,
        allow_unicode=True,
        indent=2,
        default_flow_style=False,
    )


def print_tree(tree: Union[dict, PatternTree]):
    print(dump_tree(tree))


class PatternTreeDumper(yaml.Dumper):
    """Pretty-printer for STIX2 Pattern Trees

    This dumper:
     - Indents list items past their parent keys
     - Prints empty space instead of `null`
     - Prints OrderedDicts as regular dicts
     - Prints datetimes in RFC 3339 / ISO 8601 format, with a hard requirement
         on including the UTC "Z" for timezone, as required by STIX2 spec [1]
     - Prints short lists/sets as single-line literals, instead of dashed items
         (e.g. 'path: [name]' instead of 'path:\n  - name')
     - Prints Python slice objects as plain representations of their syntax
         (e.g. slice(1) == [1] and slice(2, None, 7) == [2::7])
     - Omits mapping values with set literals

    [1]: http://docs.oasis-open.org/cti/stix/v2.0/cs01/part1-stix-core/stix-v2.0-cs01-part1-stix-core.html#_Toc496709271
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Whether to omit mapping values (for set literals). See expect_flow_mapping
        self.in_flow_set = False

        # Whether to omit mapping values and use '?' instead of '-' (for
        # multiline sets). See expect_block_mapping
        self.in_block_set = False

    def process_tag(self):
        """Disable the emission of tags (e.g. !dict)"""
        pass  # noop

    def increase_indent(self, flow=False, indentless=False):
        """Indent dashes in lists, not just items

        This will output:

            my_list:
              - item 1
              - item 2

        Instead of the default:

            my_list:
            - item 1
            - item 2

        """
        return super(PatternTreeDumper, self).increase_indent(flow, False)

    def represent_none(self, data):
        """Don't print "null" for None; only """
        return self.represent_scalar('tag:yaml.org,2002:null', '')

    def represent_pattern_tree(self, data: PatternTree):
        return self.represent_mapping('!dict', data)

    def represent_ordered_dict(self, data: OrderedDict):
        return self.represent_mapping('!dict', data.items())

    def represent_datetime(self, data: datetime):
        value = data.strftime('%Y-%m-%dT%H:%M:%SZ')
        return self.represent_scalar('tag:yaml.org,2002:timestamp', value)

    def represent_compactible_object(self, data: CompactibleObject):
        data_type = data.get_literal_type()
        representer = self.yaml_representers.get(data_type) or self.__class__.represent_data
        node = representer(self, data)
        node.flow_style = data.is_eligible_for_compaction()
        return node

    def represent_slice(self, data: slice):
        if data.step is not None:
            components = [data.start, data.stop, data.step]
        elif data.start is not None:
            components = [data.start, data.stop]
        else:
            components = [data.stop]

        s = ':'.join(
            str(comp) if comp is not None else ''
            for comp in components
        )

        return self.represent_scalar(DEFAULT_SLICE_TAG, f'[{s}]', style='')

    def expect_flow_mapping(self):
        if self.event.tag == DEFAULT_SET_TAG:
            self.in_flow_set = True
        super().expect_flow_mapping()

    def expect_first_flow_mapping_key(self):
        if isinstance(self.event, yaml.MappingEndEvent):
            self.in_flow_set = False
        super().expect_first_flow_mapping_key()

    def expect_flow_mapping_key(self):
        if isinstance(self.event, yaml.MappingEndEvent):
            self.in_flow_set = False
        super().expect_first_flow_mapping_key()

    def expect_flow_mapping_simple_value(self):
        if self.in_flow_set:
            # This branch skips writing ":" with `write_indicator(':')`, the
            # value with `expect_node(mapping=True)`, and jumps straight to the
            # next key by setting state to expect_flow_mapping_key
            self.state = self.expect_flow_mapping_key
        else:
            super().expect_flow_mapping_simple_value()

    def expect_block_mapping(self):
        if self.event.tag == DEFAULT_SET_TAG:
            self.in_block_set = True
        super().expect_block_mapping()

    def expect_block_mapping_key(self, first=False):
        if not first and isinstance(self.event, yaml.MappingEndEvent):
            self.in_block_set = False
        super().expect_block_mapping_key(first=first)

    def expect_block_mapping_value(self):
        if not self.in_block_set:
            self.write_indent()
            self.write_indicator(':', True, indention=True)
        self.states.append(self.expect_block_mapping_key)
        self.expect_node(mapping=True)

    def analyze_scalar(self, scalar):
        analysis = super().analyze_scalar(scalar)

        if self.in_block_set:
            # multiline is used, in part, to determine whether the block mapping
            # key is "simple". In case of sets, "simple" means "?" is not used
            # to prefix items — and we *do* want the "?"
            analysis.multiline = True

        if self.event.tag == DEFAULT_SLICE_TAG:
            # YAML disallows flow style (AKA literals) if the scalar begins
            # with "[". We overload the loader to allow this, so we're okay
            # allowing scalars beginning with [.
            analysis.allow_flow_plain = True
            self.style = ''

        return analysis


PatternTreeDumper.add_representer(type(None), PatternTreeDumper.represent_none)
PatternTreeDumper.add_representer(PatternTree, PatternTreeDumper.represent_pattern_tree)
PatternTreeDumper.add_representer(OrderedDict, PatternTreeDumper.represent_ordered_dict)
PatternTreeDumper.add_representer(datetime, PatternTreeDumper.represent_datetime)
PatternTreeDumper.add_multi_representer(CompactibleObject, PatternTreeDumper.represent_compactible_object)
PatternTreeDumper.add_representer(slice, PatternTreeDumper.represent_slice)


class PatternTreeLoader(yaml.Loader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Whether we've recognized an ObjectPath, and are about to descend
        # into it
        self.is_object_path = False

        # Whether we've descended into an ObjectPath, which we use to
        # construct slices instead of lists for, e.g., [1] and [*].
        self.in_object_path = False

    def compose_node(self, parent, index):
        event = self.peek_event()
        key_name = getattr(index, 'value', None)
        state = {}

        # Heuristic: any sequence whose key is "path" is presumed to be an
        # ObjectPath.
        if isinstance(event, yaml.SequenceStartEvent) and key_name == 'path':
            state['is_object_path'] = True

        with override(self, state):
            node = super().compose_node(parent, index)

        # Heuristic: any mapping whose key is "objects" is presumed to be
        # underneath an observation/expression.
        if isinstance(event, yaml.MappingStartEvent) and key_name == 'objects':
            # Heuristic: if the value of the "objects" key has no explicit YAML
            # tag, and it's using a map literal (flow_style=True), we presume
            # it's a set literal
            if event.implicit and event.flow_style:
                node.tag = DEFAULT_SET_TAG

        return node

    def compose_sequence_node(self, anchor):
        state = {}
        if self.is_object_path:
            state['in_object_path'] = True

        with override(self, state):
            node = super().compose_sequence_node(anchor)

        # Any sequences inside object paths are actually slice notation.
        # e.g. [1] is not list([1]), but slice(1)
        if self.in_object_path:
            assert isinstance(node.value, list)
            assert len(node.value) == 1

            return yaml.ScalarNode(
                DEFAULT_SLICE_TAG,
                f'[{node.value[0].value}]',
                node.start_mark,
                node.end_mark,
            )

        return node

    def scan_anchor(self, TokenClass):
        # Partial heuristic: check for start of list literal (AKA flow sequence)
        if len(self.tokens) == 1 and isinstance(self.tokens[0], yaml.FlowSequenceStartToken):
            indicator = self.peek()
            next_char = self.peek(1)

            # Heuristic: if list literal consists entirely of [*], skip treating
            # it as an alias (which asterisk normally represents)
            if indicator == '*' and next_char == ']':
                # Eat our asterisk
                self.forward(1)

                # Tell the scanner we're done with our "sequence". This will
                # append the flow sequence end token, which we'll ditch.
                self.fetch_flow_sequence_end()

                start_mark = self.tokens[0].start_mark
                end_mark = self.tokens[1].end_mark

                # Fabricated tag to ease construction, by explicitly marking
                # the type of our slice scalar — instead of relying on
                # heuristics of the ['*'] value later.
                tag_token = yaml.TagToken(('!', 'slice'), start_mark, end_mark)

                slice_token = yaml.ScalarToken(
                    value='[*]',
                    plain=False,
                    start_mark=start_mark,
                    end_mark=end_mark,
                    style='',
                )

                # Wipe out the flow sequence start and end tokens and replace
                # with our tag token, effectively removing all traces of the
                # flow sequence, and fabricating the existence of our slice
                self.tokens[:] = [tag_token]

                # This return value is appended to self.tokens
                return slice_token

        return super().scan_anchor(TokenClass)

    def construct_slice(self, node):
        contents = node.value[1:-1]  # remove [ and ]
        split_contents = contents.split(':')

        components = []
        for value in split_contents:
            try:
                value = int(value)
            except (ValueError, TypeError):
                pass
            components.append(value)

        if len(components) == 1:
            stop = components[0]
            start = step = None
        elif len(components) == 2:
            start, stop = components
            step = None
        elif len(components) == 3:
            start, stop, step = components
        else:
            raise AssertionError(
                'slices may only have three components: [start:stop:step]')

        return slice(start, stop, step)


PatternTreeLoader.add_constructor(DEFAULT_SLICE_TAG, PatternTreeLoader.construct_slice)


@contextmanager
def override(obj, _state=None, **extra):
    """Change attrs of obj within manager, then revert afterward

    Usage:

        self.stuff = 1337

        with override(self, stuff=12):
            print(self.stuff)
            # 12

        print(self.stuff)
        # 1337
    """
    if _state is None:
        _state = {}
    state = {
        **_state,
        **extra,
    }

    old_state = {k: getattr(obj, k, None) for k in state}

    for attr, value in state.items():
        setattr(obj, attr, value)

    yield

    for attr, value in old_state.items():
        setattr(obj, attr, value)
