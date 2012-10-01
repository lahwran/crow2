
import pprint
import traceback

from twisted.python.reflect import fullyQualifiedName

from .exceptions import CyclicDependencyError, ExceptionInCallError, DecoratedFuncMissingError

def topological_sort(graph_unsorted):
    """
    from http://blog.jupo.org/2012/04/06/topological-sorting-acyclic-directed-graphs/
    slightly modified, used with permission

    Repeatedly go through all of the nodes in the graph, moving each of
    the nodes that has all its edges resolved, onto a sequence that
    forms our sorted graph. A node has all of its edges resolved and
    can be moved once all the nodes its edges point to, have been moved
    from the unsorted graph onto the sorted one.
    """

    graph_sorted = []

    graph_unsorted = dict(graph_unsorted)

    while graph_unsorted:
        acyclic = False
        for node, edges in graph_unsorted.items():
            for edge in edges:
                if edge in graph_unsorted:
                    break
            else:
                acyclic = True
                del graph_unsorted[node]
                graph_sorted.append(node) # changed: we only care about the node itself

        if not acyclic:
            raise CyclicDependencyError()

    return graph_sorted

def format_args(args, keywords):
    results = []

    for arg in args:
        results.append(repr(arg))

    for key, value in keywords.items():
        results.append("%s=%r" % (key, value))

    return "(%s)" % ", ".join(results)

class LazyCall(object):
    def __init__(self, attributes, args, keywords, is_decorator=False, simple_decorator=True):
        self.attributes = attributes
        self.args = args
        self.keywords = keywords
        self.is_decorator = is_decorator
        self.simple_decorator = simple_decorator

    def _format_exception(self, exctype, message, target_obj, found_names, obj, func):
        formatted = traceback.format_exc()
        argformat = (
            "\nCALL ARGS: lazy_call%s\n"
            "args: %s\n"
            "keywords: %s\n\n") % (format_args(self.args, self.keywords), pprint.pformat(self.args), pprint.pformat(self.keywords))

        if self.is_decorator:
            if self.simple_decorator:
                argformat = ""
            else:
                argformat += "\n"

            try:
                fqname = fullyQualifiedName(func)
            except AttributeError:
                fqname = None

            argformat += "decorated func: %s: %r" % (fqname, func)

        return exctype(("Original exception: \n%s"
            "%s\n\n"
            "%r is %r.%s\n"
            "is_decorator: %r\n"
            "%s") % (formatted, message, obj, target_obj, '.'.join(found_names), self.is_decorator, argformat))

    def resolve(self, target_obj, func=None):
        obj = target_obj
        found_names = []
        for attribute in self.attributes:
            try:
                obj = getattr(obj, attribute)
            except AttributeError as e:
                raise self._format_exception(AttributeError, 
                        "While resolving lazy call: %r has no attribute %s" % (obj, attribute),
                        target_obj, found_names, obj, func)
            found_names.append(attribute)

        if self.is_decorator and func is None:
            raise self._format_exception(DecoratedFuncMissingError, "please pass me an object to decorate :<", target_obj, found_names, obj, func)

        try:
            if self.is_decorator:
                if self.simple_decorator:
                    obj(func)
                else:
                    obj(*self.args, **self.keywords)(func)
            else:
                obj(*self.args, **self.keywords)
        except Exception as e:
            raise self._format_exception(ExceptionInCallError, "Exception occured while performing lazy call", target_obj, found_names, obj, func)
        return obj

    def __repr__(self):
        
        initial = "<%s ?.%s%%s>" % (type(self).__name__, ".".join(self.attributes))
        if self.is_decorator:
            decstring = ""
            if not self.simple_decorator:
                decstring = format_args(self.args, self.keywords)
            decstring += "(<func>)"
            return initial % decstring

        return initial % format_args(self.args, self.keywords)
