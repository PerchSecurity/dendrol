from typing import Any

import antlr4
import antlr4.error.Errors
import antlr4.error.ErrorListener
import six

from .debug import print_tree
from .lang.STIXPatternLexer import STIXPatternLexer
from .lang.STIXPatternListener import STIXPatternListener
from .lang.STIXPatternParser import STIXPatternParser
from .lang.STIXPatternVisitor import STIXPatternVisitor
from .transform import PatternTreeVisitor, PatternTree


class ParserErrorListener(antlr4.error.ErrorListener.ErrorListener):
    """
    Simple error listener which just remembers the last error message received.
    """
    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        self.error_message = f'{line}:{column}: {msg}'


class ParseException(Exception):
    """Represents a parse error."""
    pass


def parse(pattern_str: str, trace: bool = False) -> STIXPatternParser.PatternContext:
    """
    Parses the given pattern and returns the antlr parse tree.

    NOTE: most of this code and comments were lifted from oasis-open/cti-pattern-validator

    :param pattern_str: The STIX pattern
    :param trace: Whether to enable debug tracing while parsing.
    :return: The parse tree
    :raises ParseException: If there is a parse error
    """
    in_ = antlr4.InputStream(pattern_str)
    lexer = STIXPatternLexer(in_)
    lexer.removeErrorListeners()  # remove the default "console" listener
    token_stream = antlr4.CommonTokenStream(lexer)

    parser = STIXPatternParser(token_stream)
    parser.removeErrorListeners()  # remove the default "console" listener
    error_listener = ParserErrorListener()
    parser.addErrorListener(error_listener)

    # I found no public API for this...
    # The default error handler tries to keep parsing, and I don't
    # think that's appropriate here.  (These error handlers are only for
    # handling the built-in RecognitionException errors.)
    parser._errHandler = antlr4.BailErrorStrategy()

    # To improve error messages, replace "<INVALID>" in the literal
    # names with symbolic names.  This is a hack, but seemed like
    # the simplest workaround.
    for i, lit_name in enumerate(parser.literalNames):
        if lit_name == u"<INVALID>":
            parser.literalNames[i] = parser.symbolicNames[i]

    parser.setTrace(trace)

    try:
        tree = parser.pattern()
    except antlr4.error.Errors.ParseCancellationException as e:
        # The cancellation exception wraps the real RecognitionException
        # which caused the parser to bail.
        real_exc = e.args[0]

        # I want to bail when the first error is hit.  But I also want
        # a decent error message.  When an error is encountered in
        # Parser.match(), the BailErrorStrategy produces the
        # ParseCancellationException.  It is not a subclass of
        # RecognitionException, so none of the 'except' clauses which would
        # normally report an error are invoked.
        #
        # Error message creation is buried in the ErrorStrategy, and I can
        # (ab)use the API to get a message: register an error listener with
        # the parser, force an error report, then get the message out of the
        # listener.  Error listener registration is above; now we force its
        # invocation.  Wish this could be cleaner...
        parser._errHandler.reportError(parser, real_exc)

        # should probably chain exceptions if we can...
        # Should I report the cancellation or recognition exception as the
        # cause...?
        six.raise_from(ParseException(error_listener.error_message),
                       real_exc)
    else:
        return tree


class Pattern:
    """A parsed pattern expression, with traversal and representation methods
    """
    tree: STIXPatternParser.PatternContext

    def __init__(self, pattern_str: str):
        """
        Compile a pattern.

        :param pattern_str: The pattern to compile
        :raises ParseException: If there is a parse error
        """
        self.tree = parse(pattern_str)

    def walk(self, listener: STIXPatternListener):
        """Walk all nodes of the parse tree
        """
        antlr4.ParseTreeWalker.DEFAULT.walk(listener, self.tree)

    def visit(self, visitor: STIXPatternVisitor) -> Any:
        """Visit nodes in the parse tree and return a value

        Unlike the listener pattern, which enumerates all nodes and gossips to
        the listener about them, a visitor determines which nodes to descend
        into, and is able to return a value for each.
        """
        return self.tree.accept(visitor)

    def to_dict_tree(self) -> PatternTree:
        """Convert the parse tree to a simplified dict tree

        See dendrol.transform.DictVisitor for more info
        """
        visitor = PatternTreeVisitor()
        return visitor.visit(self.tree)

    def print_dict_tree(self):
        """Print a human-consumable representation of the dict tree to console
        """
        print_tree(self.to_dict_tree())
