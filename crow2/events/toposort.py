"""
from http://blog.jupo.org/2012/04/06/topological-sorting-acyclic-directed-graphs/
slightly modified, used with permission
"""

from .exceptions import CyclicDependencyError

def topological_sort(graph_unsorted):
    """
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
