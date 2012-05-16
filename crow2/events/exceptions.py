
from crow2.util import ExceptionWithMessage

# long exception names are fun /s
class DependencyMissingError(ExceptionWithMessage):
    "{0!r}: Could not resolve dependency {1!r} of dep-res node {2!r}"

class DuplicateRegistrationError(Exception):
    "Handler[s] was/were already registered, but something tried to register them again"

class InvalidOrderRequirementsError(ExceptionWithMessage):
    "{0!r} registered to {1!r} with both tag and dependency"

class NotRegisteredError(Exception):
    "Raised when an unregister is attempted for a registration which is not registered"

class NameResolutionError(Exception):
    "Raised when dependency resolution fails to locate an appropriate handler with a provided name"

class NotInstantiableError(Exception):
    "Raised when a class registered for instantiation cannot be instantiated"

class AlreadyRegisteredError(Exception):
    "Raised when a registration is attempted on an object which is already registered"

class CyclicDependencyError(Exception):
    "Raised when there is an unresolvable dependency loop"

