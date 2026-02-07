"""
Main endpoint for users.
Exposes a `batchify` function that maps a target object (function or instance)
to a BatchingProxy object that activates a specific Batcher context
whenever any method on the wrapped object is called.
"""


def batchify(target, **kwargs):
    """
    Universal adapter.

    Args:
        target: Function or Object (Client, Agent, etc.)
        **kwargs: Batcher configuration

    Returns:
        Wrapped target (Proxy or decorated function)
    """
    # 1. install_hooks()
    # 2. Create Batcher(**kwargs)
    # 3. If callable(target): return decorated_function
    # 4. If object: return BatchingProxy(target, batcher)
