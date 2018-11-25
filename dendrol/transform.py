import base64
import binascii
from collections import OrderedDict
from datetime import date, datetime, tzinfo
from typing import Iterable, List, Type, Union, Set, TypeVar, NewType, Dict

from . import tz
from .lang.STIXPatternParser import STIXPatternParser, ParserRuleContext
from .lang.STIXPatternVisitor import STIXPatternVisitor


ConvertedStixLiteral = NewType('ConvertedStixLiteral', Union[
    int,
    str,
    bool,
    float,
    bytes,
    datetime,
])


class PatternTree(dict):
    """dict-based tree structure representing a STIX2 Pattern Expression

    OrderedDicts and some specialized subclasses of Python primitives are used
    to to offer a human-consumable YAML representation.
    See dendrol.debug.PatternTreeDumper for more info.
    """

    def __str__(self):
        return self.serialize()

    def serialize(self):
        from .debug import dump_tree
        return dump_tree(self)

    @classmethod
    def from_dict(cls, d: dict) -> 'PatternTree':
        """Transform a regular Python dict to PatternTree's types and orderings

        XXX: a more holistic/less context-dependent way of doing this (and all
             the format methods below) might be using OrderedDict subclasses
             for each node type (CompositeObservation, SimpleComparison, etc)
        """
        if d.keys() != {'pattern'}:
            raise ValueError('Expected a dict with one top-level key, "pattern"')

        tree = PatternTree(d)

        # We will walk the tree, updating nodes as we go, and collecting next
        # nodes to visit in these lists
        observations = [d['pattern']]
        qualifiers = []
        comparisons = []

        OBSERVATION_TYPES = {
            'expression': cls.format_composite_observation,
            'observation': cls.format_simple_observation,
        }

        # Walk all observations, formatting each as we go, saving child
        # observations for successive iterations, and any qualifiers and
        # comparisons for the next stages
        while observations:
            node = observations.pop()
            assert len(node) == 1, \
                'Each observation must be a dict with a single key-value pair'

            node_type, body = next(iter(node.items()))
            if node_type not in OBSERVATION_TYPES:
                raise ValueError(
                    f'Unexpected observation type {repr(node_type)}. '
                    f'Expected one of: {OBSERVATION_TYPES.keys()}')

            formatter = OBSERVATION_TYPES[node_type]
            node.update(formatter(**body))
            new_body = next(iter(node.values()))

            if node_type == 'expression':
                observations.extend(new_body['expressions'])
            elif node_type == 'observation':
                comparisons.extend(new_body['expressions'])

            qualifiers.extend(new_body['qualifiers'] or ())

        QUALIFIER_TYPES = {
            'start_stop': cls.format_start_stop_qualifier,
            'within': cls.format_within_qualifier,
            'repeats': cls.format_repeats_qualifier,
        }

        # Because qualifiers are not nested, we can iterate through them with
        # a simple for-loop
        for qualifier in qualifiers:
            assert len(qualifier) == 1, \
                'Each qualifier must be a dict with a single key-value pair'

            qualifier_type, body = next(iter(qualifier.items()))
            if qualifier_type not in QUALIFIER_TYPES:
                raise ValueError(
                    f'Unexpected qualifier type {repr(qualifier_type)}. '
                    f'Expected one of: {QUALIFIER_TYPES.keys()}')

            formatter = QUALIFIER_TYPES[qualifier_type]
            qualifier.update(formatter(**body))

        COMPARISON_TYPES = {
            'expression': cls.format_composite_comparison,
            'comparison': cls.format_simple_comparison,
        }

        # Comparisons may have children, so we convert each node as we iterate,
        # and collect any children for successive iterations
        while comparisons:
            node = comparisons.pop()
            assert len(node) == 1, \
                'Each comparison must be a dict with a single key-value pair'

            node_type, body = next(iter(node.items()))
            if node_type not in COMPARISON_TYPES:
                raise ValueError(
                    f'Unexpected comparison type {repr(node_type)}. '
                    f'Expected one of: {COMPARISON_TYPES.keys()}')

            formatter = COMPARISON_TYPES[node_type]
            node.update(formatter(**body))
            new_body = next(iter(node.values()))

            if 'expression' in node:
                comparisons.extend(new_body['expressions'])

        return tree

    @classmethod
    def format_pattern(cls, *, root: dict):
        return cls(pattern=root)

    @classmethod
    def format_composite_observation(cls, *,
                                     expressions: List[Dict[str, dict]],
                                     join: str = None,
                                     qualifiers: List[Dict[str, dict]] = None,
                                     ) -> Dict[str, OrderedDict]:
        return {
            'expression': OrderedDict([
                ('join', join),
                ('qualifiers', qualifiers),
                ('expressions', expressions),
            ]),
        }

    @classmethod
    def format_simple_observation(cls, *,
                                  objects: Iterable[str],
                                  expressions: List[Dict[str, dict]],
                                  join: str = None,
                                  qualifiers: List[Dict[str, dict]] = None,
                                  ) -> Dict[str, OrderedDict]:
        if not isinstance(objects, ObjectTypeSet):
            objects = ObjectTypeSet(objects)

        return {
            'observation': OrderedDict([
                ('objects', objects),
                ('join', join),  # XXX: should this be allowed?
                                 # I kinda figured it would be convenient to rollup the first
                                 # composite comparison into its parent observation... but this
                                 # may make traversal implementations cumbersome.
                ('qualifiers', qualifiers),
                ('expressions', expressions),
            ]),
        }

    @classmethod
    def format_composite_comparison(cls, *,
                                    expressions: List[Dict[str, dict]],
                                    join: str = None,
                                    ) -> Dict[str, OrderedDict]:
        return {
            'expression': OrderedDict([
                ('join', join),
                ('expressions', expressions),
            ]),
        }

    @classmethod
    def format_simple_comparison(cls, *,
                                 object: str,
                                 path: List[Union[str, slice]],
                                 operator: str,
                                 value: ConvertedStixLiteral,
                                 negated: bool = None,
                                 ) -> Dict[str, OrderedDict]:
        if not isinstance(path, ObjectPath):
            # Converting path to our special type ensures uniform string
            # representations, enabling useful text diffing.
            path = ObjectPath(path)

        return {
            'comparison': OrderedDict([
                ('object', object),
                ('path', path),
                ('negated', negated),
                ('operator', operator),
                ('value', cls.format_literal(value)),
            ]),
        }

    @classmethod
    def format_start_stop_qualifier(cls, *,
                                    start: datetime,
                                    stop: datetime,
                                    ) -> Dict[str, OrderedDict]:
        return {
            'start_stop': OrderedDict([
                ('start', cls.format_literal(start)),
                ('stop', cls.format_literal(stop)),
            ])
        }

    @classmethod
    def format_within_qualifier(cls, *,
                                value: int,
                                unit: str = 'SECONDS',
                                ) -> Dict[str, OrderedDict]:
        return {
            'within': OrderedDict([
                ('value', cls.format_literal(value)),
                ('unit', unit),
            ])
        }

    @classmethod
    def format_repeats_qualifier(cls, *, value: int) -> Dict[str, OrderedDict]:
        return {
            'repeats': OrderedDict([
                ('value', cls.format_literal(value)),
            ])
        }

    @classmethod
    def format_object_path(cls, *, object: str, path: List[Union[str, slice]]):
        return OrderedDict([
            ('object', object),
            ('path', path),
        ])

    @classmethod
    def format_literal(cls, literal):
        if isinstance(literal, datetime):
            if literal.tzinfo is None:
                literal = literal.replace(tzinfo=tz.utc())
            elif not is_utc(literal):
                raise ValueError('All datetimes must be in UTC')
        return literal


class CompactibleObject:
    """Base class which instructs the YAML dumper when to use literal syntax

    For example, lists with single component can be dumped as list literals by
    overriding and returning True from is_eligible_for_compaction().

    >>> class CompactMe(CompactibleObject, list):
    ...     def is_eligible_for_compaction(self):
    ...         return True
    ...
    >>> from dendrol import print_tree
    >>> print_tree({'path': CompactMe(['name'])})
    path: [name]
    >>> class DontCompactOnMe(CompactibleObject, list):
    ...     def is_eligible_for_compaction(self):
    ...         return False
    ...
    >>> print_tree({'path': DontCompactOnMe(['name'])})
    path:
      - name
    """

    def is_eligible_for_compaction(self) -> bool:
        """Whether this object could be represented on one line"""
        return False

    def get_literal_type(self) -> Type:
        """Return the type of literal this object is represented as

        By default, this returns the first non-CompactibleObject base class in
        the object's method resolution order (MRO).
        """
        for klass in self.__class__.__mro__:
            if issubclass(klass, CompactibleObject):
                continue

            # Heuristic: ignore type-hinting classes
            if klass.__module__ == 'typing':
                continue

            return klass

        raise NotImplementedError(
            'This CompactibleObject has no obvious literal type. '
            'Please override the get_literal_type() method.')


class CompactibleList(CompactibleObject, list):
    pass


class CompactibleSet(CompactibleObject, set):
    pass


class ObjectTypeSet(CompactibleSet, Set[str]):
    def is_eligible_for_compaction(self) -> bool:
        return len(self) == 1


class ObjectPath(CompactibleList):
    def is_eligible_for_compaction(self) -> bool:
        return len(self) == 1


class PatternTreeVisitor(STIXPatternVisitor):
    """Converts a STIX2 Pattern into a PatternTree, by selectively descending

    BACKGROUND ::

        The Visitor pattern differs from the Listener pattern (which has the
        characteristic enterXYZ/exitXYZ methods) in that instead of visiting
        each symbol (and calling those enter/exit methods for each), a Visitor
        is responsible for selecting which symbols to descend into. By way of
        analogy, this is akin to finding the quickest route through a forest
        by following the trail markers, rather than trying all routes, drawing
        a map of them, and ignoring all the long ones.

        Unlike the Listener pattern, where any output must be a side effect —
        some state stored in the class, built up incrementally — a Visitor is
        in control of its return value. This makes development of parse tree
        transformers a breeze: just figure out what a symbol ought to look like
        in the end result, then figure out how those things ought to be
        combined — rinse, repeat until all symbols are covered.


    IMPLEMENTATION ::

        The self.visit method is responsible for accepting an arbitrary symbol
        and calling the appropriate self.visitXYZ method specific to the type —
        AKA dispatch.

        The root node in all pattern expressions is the Pattern symbol.
        Execution of PatternTreeVisitor thusly always begins in visitPattern.

        Step through with a debugger, and it can seem like execution jumps all
        around the file — behind the scenes, though, the Visitor acts like a
        decision tree: for each symbol, a specific visitXYZ or generic emitYYZ
        method must decide which components to ignore, which to include as data
        in the PatternTree, and which to descend into (so the same can be done
        with them).

        Bit by bit, each symbol is transformed into PatternTree form, till
        visitPattern finally returns with the end result.

    """

    def visitPattern(self,
                     ctx: STIXPatternParser.PatternContext,
                     ) -> PatternTree:
        """Convert the root node, Pattern, into a PatternTree"""
        return self.emitPattern(ctx)


    ##########################
    # COMPOSITE OBSERVATIONS #
    ##########################
    #
    # The STIX2 grammar uses parent symbols to join 1 or more
    # observations/expressions together by one of the FOLLOWEDBY, OR, or AND
    # operators. All observations, regardless of whether they're joined to
    # another expression, are children to these parent link symbols.
    #
    # FOLLOWEDBY corresponds to the observationExpressions symbol;
    # OR to observationExpressionOR; and AND to observationExpressionAnd.
    #
    # Though the grammar does not formally name this class of symbols,
    # I (zkanzler) figured "composite observation" described it well, and made
    # it easy to discern from other symbol classes used in PatternTree parsing.
    #
    # The emitCompositeObservation method is used to convert each type of
    # parent symbols into PatternTree form, simply storing the join operator's
    # text in the PatternTree to differentiate each symbol type.
    #
    def visitObservationExpressions(self, ctx: STIXPatternParser.ObservationExpressionsContext):
        """Convert <obs_expr> FOLLOWEDBY <obs_expr2> into PatternTree form"""
        return self.emitCompositeObservation(ctx)

    def visitObservationExpressionOr(self, ctx: STIXPatternParser.ObservationExpressionOrContext):
        """Convert <obs_expr> OR <obs_expr2> into PatternTree form"""
        return self.emitCompositeObservation(ctx)

    def visitObservationExpressionAnd(self, ctx: STIXPatternParser.ObservationExpressionAndContext):
        """Convert <obs_expr> AND <obs_expr2> into PatternTree form"""
        return self.emitCompositeObservation(ctx)

    def visitObservationExpressionCompound(self, ctx: STIXPatternParser.ObservationExpressionCompoundContext):
        """Ditch parens around an observation expression"""
        lparen, expr, rparen = ctx.getChildren()
        return self.visit(expr)

    #######################
    # SIMPLE OBSERVATIONS #
    #######################
    #
    # Whereas a "composite observation" joins two or more observations and/or
    # expressions by an operator, a "simple observation" is a bare observation,
    # below which (in the tree) no further composite observations may occur —
    # only comparisons/expressions may be found.
    #
    # The grammar deems this observationExpressionSimple, the naming of which
    # inspired the terms used in PatternTree parsing for other classes of
    # symbols (e.g. simple comparison, composite comparison).
    #
    def visitObservationExpressionSimple(self, ctx: STIXPatternParser.ObservationExpressionSimpleContext):
        return self.emitSimpleObservation(ctx)

    ##########################
    # OBSERVATION QUALIFIERS #
    ##########################
    #
    # The STIX2 grammar uses a parent symbol to link an observation/expression
    # to an actual qualifier symbol. These parent symbols are named in the form
    # observationExpression<QualifierName>. The qualifier symbols are named
    # <qualifierName>Qualifier.
    #
    # We use the generic emitObservationQualifier method to add all the
    # qualifiers of an observation expression (by flattening the subtree) to
    # its PatternTree form. The qualifiers are converted to PatternTree form
    # in the overridden visit<QualifierName>Qualifier methods.
    #
    def visitObservationExpressionStartStop(self, ctx: STIXPatternParser.ObservationExpressionStartStopContext):
        return self.emitObservationQualifier(ctx)

    def visitObservationExpressionWithin(self, ctx: STIXPatternParser.ObservationExpressionWithinContext):
        return self.emitObservationQualifier(ctx)

    def visitObservationExpressionRepeated(self, ctx: STIXPatternParser.ObservationExpressionRepeatedContext):
        return self.emitObservationQualifier(ctx)

    def visitStartStopQualifier(self, ctx: STIXPatternParser.StartStopQualifierContext):
        """Convert <expr> START <start_dt> STOP <stop_dt> qualifier into PatternTree form

        See PatternTree.format_start_stop_qualifier for returned structure
        """
        start, start_dt, stop, stop_dt = ctx.getChildren()
        return PatternTree.format_start_stop_qualifier(
            start=self.visit(start_dt),
            stop=self.visit(stop_dt),
        )

    def visitWithinQualifier(self, ctx: STIXPatternParser.WithinQualifierContext):
        """Convert <expr> WITHIN <number> SECONDS qualifier into PatternTree form
        """
        within, number, unit = ctx.getChildren()
        return PatternTree.format_within_qualifier(
            value=self.visit(number),
            unit=self.visit(unit),
        )

    def visitRepeatedQualifier(self, ctx:STIXPatternParser.RepeatedQualifierContext):
        repeats, number, times = ctx.getChildren()
        return PatternTree.format_repeats_qualifier(
            value=self.visit(number),
        )

    #########################
    # COMPOSITE COMPARISONS #
    #########################
    #
    # The STIX2 grammar uses the comparisonExpression symbol to denote 1 or
    # more simple or composite comparisons, joined by OR. Below this in the
    # hierarchy, comparisonExpressionAnd does the same for AND.
    #
    # NOTE: this means all comparison expressions, regardless of whether they
    #       are joined by OR/AND, sit below a comparisonExpression and
    #       comparisonExpressionAnd symbol.
    #
    # Though the grammar does not formally name this type of symbol
    # representing a joined group of comparisons & comparison expressions,
    # I (zkanzler) figured "composite comparison"
    #
    # Composite comparisons are handled by the generic emitCompositeComparison,
    # which is able to determine which join operator is used by reading the
    # symbol type.
    #
    def visitComparisonExpression(self, ctx: STIXPatternParser.ComparisonExpressionContext):
        return self.emitCompositeComparison(ctx)

    def visitComparisonExpressionAnd(self, ctx: STIXPatternParser.ComparisonExpressionAndContext):
        return self.emitCompositeComparison(ctx)

    ######################
    # SIMPLE COMPARISONS #
    ######################
    #
    # PropTests are the actual comparisons of an object's property to a literal
    # value, e.g. `file:name = "test"`. There is one symbol for each type of
    # comparison operator.
    #
    # STIX2 deems them "property tests", which are aptly named for their
    # function — but I (zkanzler) think "simple comparison" uniquely identifies
    # their role in reference to all other types of expressions.
    #
    # All types of comparisons are handled by the generic emitSimpleComparison,
    # which, at time of writing (2018/11/20), simply stores the text of the
    # operator to differentiate each symbol type — each propTest symbol has the
    # same <NOT>? <LHS> <OP> <RHS> syntax.
    #
    def visitPropTestEqual(self, ctx: STIXPatternParser.PropTestEqualContext):
        return self.emitSimpleComparison(ctx)

    def visitPropTestOrder(self, ctx: STIXPatternParser.PropTestOrderContext):
        return self.emitSimpleComparison(ctx)

    def visitPropTestSet(self, ctx: STIXPatternParser.PropTestSetContext):
        return self.emitSimpleComparison(ctx)

    def visitPropTestLike(self, ctx: STIXPatternParser.PropTestLikeContext):
        return self.emitSimpleComparison(ctx)

    def visitPropTestRegex(self, ctx: STIXPatternParser.PropTestRegexContext):
        return self.emitSimpleComparison(ctx)

    def visitPropTestIsSubset(self, ctx: STIXPatternParser.PropTestIsSubsetContext):
        return self.emitSimpleComparison(ctx)

    def visitPropTestIsSuperset(self, ctx: STIXPatternParser.PropTestIsSupersetContext):
        return self.emitSimpleComparison(ctx)

    def visitPropTestParen(self, ctx: STIXPatternParser.PropTestParenContext):
        """Strips a parenthesized cmp expr and processes only its body

        Conversion is deferred to other visitPropTestXYZ methods (dispatch is
        handled by self.visit).

        Example (pseudo-code):

            visitPropTestParen('(file:name = "test" AND file:size > 12)') ==
                visit('file:name = "test" AND file:size > 12')

        """
        lparen, expr, rparen = ctx.getChildren()
        return self.visit(expr)

    def visitObjectPath(self, ctx: STIXPatternParser.ObjectPathContext):
        """Split an object path into component "object" and "path" parts

        Example (pseudo-code):

            visitObjectPath('file:name.decoded') == {
                'object': 'file',
                'path': ['name', 'decoded'],
            }

        """
        # NOTE: path will contain 0 or 1 symbols
        object_type, colon, property, *path = ctx.getChildren()
        assert not path or len(path) == 1

        # This will store the converted object path symbols, flattened from
        # tree form into a convenient list.
        full_path = [self.visit(property)]

        # Past the first property, which is a special case, if the object path
        # has two or more components (three or more in total), path[0] will be
        # a PathStep symbol, which is flattened into a list by visitPathStep.
        # If there is only one component (two in total), path[0] will be a
        # single symbol, requiring no flattening.
        if path:
            path_component: STIXPatternParser.ObjectPathComponentContext = path[0]
            if isinstance(path_component, STIXPatternParser.PathStepContext):
                full_path += self.visit(path_component)
            else:
                full_path.append(self.visit(path_component))

        return PatternTree.format_object_path(
            object=object_type.getText(),
            path=ObjectPath(full_path),
        )

    def visitPathStep(self,
                      ctx: STIXPatternParser.PathStepContext,
                      ) -> List[Union[ConvertedStixLiteral, slice]]:
        """Flatten object path steps into list of literals or slices (for [1] notation)

        Example (pseudo-code):

            visitPathStep('test.muffin[2]') == ['test', 'muffin', slice(None, 2, None)]

        """
        children = flatten_left(ctx)
        return [
            self.visit(child)
            for child in children
        ]

    def visitIndexPathStep(self, ctx: STIXPatternParser.IndexPathStepContext) -> slice:
        """Convert array/object-prop notation into a Python slice

        NOTE: the special [*] case (for "match ANY items in the array/object")
             is converted into slice(None, '*', None)
        """
        lbracket, index, rbracket = ctx.getChildren()
        return slice(self.emitLiteral(index))

    def visitFirstPathComponent(self, ctx: STIXPatternParser.FirstPathComponentContext) -> ConvertedStixLiteral:
        """Convert the first step of an object path into string form

        BACKGROUND: (I speculate) the reason for a separate, special path
                    symbol for the first step is so the grammar can enforce the
                    constraint that all object paths must have at least *one*
                    step.
        """
        return self.emitLiteral(ctx.getChild(0))

    def visitKeyPathStep(self, ctx: STIXPatternParser.KeyPathStepContext) -> ConvertedStixLiteral:
        """Convert a regular property path step (past the first) into a string
        """
        dot, key = ctx.getChildren()
        return self.emitLiteral(key)

    def visitTerminal(self, node) -> ConvertedStixLiteral:
        """Convert non-symbol nodes to Python literals

        Non-symbol nodes include string literals, names, etc
        """
        return self.emitLiteral(node)

    def emitPattern(self, ctx: STIXPatternParser.PatternContext):
        """Convert a Pattern symbol into PatternTree form

        See PatternTree.format_pattern for returned structure
        """
        observations, eof = ctx.getChildren()
        return PatternTree.format_pattern(
            root=self.visit(observations),
        )

    def emitCompositeObservation(self,
                                 ctx: Union[STIXPatternParser.ObservationExpressionsContext,
                                            STIXPatternParser.ObservationExpressionOrContext,
                                            STIXPatternParser.ObservationExpressionAndContext],
                                 ) -> dict:
        """Convert a group of joined observations into PatternTree form

        A "composite observation" is any observations joined by FOLLOWEDBY, OR,
        or AND.

        See PatternTree.format_composite_observation for returned structure
        """
        if ctx.getChildCount() == 1:
            return self.visit(ctx.getChild(0))

        op = ctx.getChild(1)
        children = flatten_left(ctx)

        return PatternTree.format_composite_observation(
            join=op.getText().upper(),
            qualifiers=None,  # if there are any qualifiers, they will be added
                              # by the parent node (which contains this
                              # expression and the qualifier)
            expressions=[
               self.visit(child)
               for child in children
           ],
        )

    def emitSimpleObservation(self, ctx: STIXPatternParser.ObservationExpressionSimpleContext):
        """Convert a non-grouped observation to its PatternTree form

        A "simple observation" is a whole observation and its child
        comparisons, including the square brackets.

        See PatternTree.format_simple_observation for returned structure
        """
        lbracket, child, rbracket = ctx.getChildren()
        root = self.visit(child)

        if 'expression' in root:
            expression = root['expression']
            join = expression['join']
            expressions = expression['expressions']
        else:
            join = None
            expressions = [root]

        object_types = self.findObjectTypes(expressions)

        return PatternTree.format_simple_observation(
            objects=object_types,
            join=join,
            expressions=expressions,
        )

    def emitObservationQualifier(self, ctx: Union[STIXPatternParser.ObservationExpressionStartStopContext,
                                                  STIXPatternParser.ObservationExpressionWithinContext,
                                                  STIXPatternParser.ObservationExpressionRepeatedContext]):
        """Add an observation expression's qualifiers in its PatternTree form

        The STIX2 Pattern grammar places the symbol linking an observation
        expression to its qualifier(s) above the observation expression in the
        tree. Because an observation expression can exist without qualifiers
        (and without a qualifier link symbol), we use self.visit() to grab the
        PatternTree form of the observation expression and update it with the
        PatternTree-converted qualifiers — instead of generating a stub of the
        observation expression's structure here, then filling it when
        processing the observation expression.

        NOTE: see PatternTree.format_composite_observation
              and PatternTree.format_simple_observation for returned structure
        """
        # NOTE: qualifiers will have 1 or more qualifier symbols
        expr, *qualifiers = flatten_left(ctx, [
            STIXPatternParser.ObservationExpressionStartStopContext,
            STIXPatternParser.ObservationExpressionWithinContext,
            STIXPatternParser.ObservationExpressionRepeatedContext,
        ])

        # node will either be {"expression": body} or {"observation": body}
        node: dict = self.visit(expr)
        assert isinstance(node, dict) and len(node) == 1  # sanity check

        # body will contain the meat of the observation/expression, which we
        # will fill with our qualifier info.
        body = next(iter(node.values()))

        body['qualifiers'] = [
            self.visit(qualifier)
            for qualifier in qualifiers
        ]
        return node


    def emitCompositeComparison(self, ctx: Union[STIXPatternParser.ComparisonExpressionContext,
                                                 STIXPatternParser.ComparisonExpressionAndContext]):
        """Convert a group of joined comparisons into PatternTree form

        See PatternTree.format_composite_comparison for returned structure.
        """
        if ctx.getChildCount() == 1:
            return self.visit(ctx.getChild(0))

        op = ctx.getChild(1)
        children = flatten_left(ctx)

        return PatternTree.format_composite_comparison(
            join=op.getText().upper(),
            expressions=[
               self.visit(child)
               for child in children
           ],
        )

    def emitSimpleComparison(self, ctx: STIXPatternParser.PropTestContext) -> dict:
        """Convert a comparison (AKA propTest) into PatternTree form

        See PatternTree.format_simple_comparison for returned structure.
        """
        lhs, *nots, op, rhs = ctx.getChildren()

        return PatternTree.format_simple_comparison(
            **self.visit(lhs),
            negated=True if nots else None,  # using None makes for an uncluttered yaml tree,
                                             # where the field will just be empty -- we only
                                             # need to see the value if it's True.
            operator=op.getText(),
            value=self.visit(rhs),
        )

    def emitLiteral(self, literal) -> ConvertedStixLiteral:
        """Convert terminal node or identifier-like sym into Python primitives
        """
        text = literal.getText()
        symbol_type = literal.getSymbol().type
        return coerce_literal(text, symbol_type)

    def findObjectTypes(self, comparison_expressions: List[dict]) -> ObjectTypeSet:
        """Find the object types used by the given comparison expressions
        """
        encountered_types = ObjectTypeSet()
        to_visit = list(comparison_expressions)

        while to_visit:
            node = to_visit.pop()
            assert isinstance(node, dict) and len(node) == 1

            node_type, body = next(iter(node.items()))

            if node_type == 'expression':
                to_visit.extend(body['expressions'])
            elif node_type == 'comparison':
                encountered_types.add(body['object'])

        return encountered_types


T = TypeVar('T', bound=ParserRuleContext)


def flatten_left(ctx: ParserRuleContext,
                 rules: Iterable[Type[T]]=None,
                 ) -> List[T]:
    r"""Flatten left-associative symbols

    Composite expressions joined with AND/OR/etc are left-associative
    (their trees expand recursively on the left-hand side). This method
    traverses down the left, recording all symbols of the same rule type
    and returning a flat representation of a homogeneous tree.

    NOTE: this method preserves only the rightmost node of each matching rule

        Example: a FOLLOWEDBY b FOLLOWEDBY c AND d

        Parens: (a FOLLOWEDBY (b FOLLOWEDBY (c AND d))

        Binary Tree (max two children):
                    FOLLOWEDBY          <-+
                   /          \           |--- Each FOLLOWEDBY has two children
            FOLLOWEDBY       AND        <-+
               /  \         /   \
              a   b        c     d

        Regular Tree:
                    FOLLOWEDBY
                   /    |     \
                  a     b    AND          <--- Single FOLLOWEDBY with all children
                            /   \
                           c     d
    """
    rules = tuple(rules or (type(ctx),))

    flattened = []
    last_lhs = ctx
    while True:
        lhs, *others = last_lhs.getChildren()
        if others:
            flattened.append(others[-1])

        if isinstance(lhs, rules):
            last_lhs = lhs
            continue
        else:
            flattened.append(lhs)
            break

    # Because insertion is O(n) in CPython, we use the O(1) append and return
    # the list in reverse.
    # ref: https://wiki.python.org/moin/TimeComplexity#list
    return list(reversed(flattened))


# NOTE: this was lifted from oasis-open/cti-pattern-matcher
def convert_stix_datetime(timestamp_str: str, ignore_case: bool=False) -> datetime:
    """
    Convert a timestamp string from a pattern to a datetime.datetime object.
    If conversion fails, raises a ValueError.
    """

    # strptime() appears to work case-insensitively.  I think we require
    # case-sensitivity for timestamp literals inside patterns and JSON
    # (for the "T" and "Z" chars).  So check case first.
    if not ignore_case and any(c.islower() for c in timestamp_str):
        raise ValueError(f'Invalid timestamp format (require upper case): {timestamp_str}')

    # Can't create a pattern with an optional part... so use two patterns
    if '.' in timestamp_str:
        fmt = '%Y-%m-%dT%H:%M:%S.%fZ'
    else:
        fmt = '%Y-%m-%dT%H:%M:%SZ'

    dt = datetime.strptime(timestamp_str, fmt)
    dt = dt.replace(tzinfo=tz.utc())

    return dt


def is_utc(o: Union[tzinfo, datetime, date]) -> bool:
    """Return whether the timezone or date/time object is (in) UTC
    """
    if isinstance(o, (datetime, date)):
        if o.tzinfo is None:
            return False
        o = o.tzinfo

    arbitrary_dt = datetime.now().replace(tzinfo=o)
    return arbitrary_dt.utcoffset().total_seconds() == 0


# NOTE: this was lifted from oasis-open/cti-pattern-matcher
PRIMITIVE_COERCERS = {
    STIXPatternParser.IntPosLiteral: int,
    STIXPatternParser.IntNegLiteral: int,
    STIXPatternParser.StringLiteral: lambda s: s[1:-1].replace("\\'", "'").replace('\\\\', '\\'),
    STIXPatternParser.BoolLiteral: lambda s: s.lower() == 'true',
    STIXPatternParser.FloatPosLiteral: float,
    STIXPatternParser.FloatNegLiteral: float,
    STIXPatternParser.BinaryLiteral: lambda s: base64.standard_b64decode(s[2:-1]),
    STIXPatternParser.HexLiteral: lambda s: binascii.a2b_hex(s[2:-1]),
    STIXPatternParser.TimestampLiteral: lambda t: convert_stix_datetime(t[2:-1]),
}


def coerce_literal(text: str,
                   symbol_type: int,
                   ) -> ConvertedStixLiteral:
    """Convert a parsed literal symbol into a Python primitive

    NOTE: If the literal type is not recognized, the original text is returned.
    """
    coercer = PRIMITIVE_COERCERS.get(symbol_type)
    return coercer(text) if coercer else text
