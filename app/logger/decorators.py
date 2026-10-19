import functools
import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from typing import cast

MILLISECONDS_PER_SECOND: int = 1000
SELF_PARAMETER: str = "self"
PATH_SEPARATOR: str = "."


type CallHook = Callable[..., None]


def log_debug[**P, R](function: Callable[P, R]) -> Callable[P, R]:
    logger: logging.Logger = logging.getLogger(name=function.__module__)
    name: str = function.__qualname__

    def on_call(*, arguments: dict[str, object]) -> None:
        if logger.isEnabledFor(level=logging.DEBUG):
            logger.debug(msg=f"{name} called with {arguments!r}")

    def on_return(*, arguments: dict[str, object], result: object, duration_ms: float) -> None:
        if logger.isEnabledFor(level=logging.DEBUG):
            logger.debug(
                msg=f"{name} returned {result!r} in {duration_ms} ms", extra={"duration_ms": duration_ms}
            )

    def on_error(*, arguments: dict[str, object], error: Exception, duration_ms: float) -> None:
        logger.debug(msg=f"{name} raised {error!r} in {duration_ms} ms", extra={"duration_ms": duration_ms})

    return wrap_call(function=function, on_call=on_call, on_return=on_return, on_error=on_error)


def log_info[**P, R](
    *, inputs: tuple[str, ...] = (), outputs: tuple[str, ...] = ()
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        logger: logging.Logger = logging.getLogger(name=function.__module__)
        name: str = function.__qualname__

        def on_call(*, arguments: dict[str, object]) -> None:
            pass

        def on_return(*, arguments: dict[str, object], result: object, duration_ms: float) -> None:
            picked_inputs: dict[str, object] = pick_inputs(arguments=arguments, paths=inputs)
            picked_outputs: dict[str, object] = {
                path: read_path(source=result, path=path) for path in outputs
            }
            summary: str = f"{joined(values=picked_inputs)} -> {joined(values=picked_outputs)}"
            logger.info(
                msg=f"{name} {summary} in {duration_ms} ms",
                extra={"inputs": picked_inputs, "outputs": picked_outputs, "duration_ms": duration_ms},
            )

        def on_error(*, arguments: dict[str, object], error: Exception, duration_ms: float) -> None:
            picked_inputs: dict[str, object] = pick_inputs(arguments=arguments, paths=inputs)
            logger.info(
                msg=f"{name} {joined(values=picked_inputs)} -> {type(error).__name__} in {duration_ms} ms",
                extra={"inputs": picked_inputs, "error": type(error).__name__, "duration_ms": duration_ms},
            )

        return wrap_call(function=function, on_call=on_call, on_return=on_return, on_error=on_error)

    return decorate


def pick_inputs(*, arguments: dict[str, object], paths: tuple[str, ...]) -> dict[str, object]:
    return {path: read_argument(arguments=arguments, path=path) for path in paths}


def read_argument(*, arguments: dict[str, object], path: str) -> object:
    argument_name, _, attribute_path = path.partition(PATH_SEPARATOR)
    return read_path(source=arguments[argument_name], path=attribute_path)


def read_path(*, source: object, path: str) -> object:
    if not path:
        return source
    return functools.reduce(getattr, path.split(PATH_SEPARATOR), source)


def joined(*, values: dict[str, object]) -> str:
    return " ".join(str(value) for value in values.values())


def wrap_call[**P, R](
    *, function: Callable[P, R], on_call: CallHook, on_return: CallHook, on_error: CallHook
) -> Callable[P, R]:
    signature: inspect.Signature = inspect.signature(obj=function)

    def arguments_of(*args: object, **kwargs: object) -> dict[str, object]:
        bound: dict[str, object] = signature.bind(*args, **kwargs).arguments
        return {name: value for name, value in bound.items() if name != SELF_PARAMETER}

    if inspect.iscoroutinefunction(obj=function):
        coroutine_function: Callable[P, Awaitable[object]] = cast(Callable[P, Awaitable[object]], function)

        @functools.wraps(wrapped=function)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
            arguments: dict[str, object] = arguments_of(*args, **kwargs)
            on_call(arguments=arguments)
            started: float = time.perf_counter()
            try:
                result: object = await coroutine_function(*args, **kwargs)
            except Exception as error:
                on_error(arguments=arguments, error=error, duration_ms=elapsed_ms(started=started))
                raise
            on_return(arguments=arguments, result=result, duration_ms=elapsed_ms(started=started))
            return result

        return cast(Callable[P, R], async_wrapper)

    @functools.wraps(wrapped=function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        arguments: dict[str, object] = arguments_of(*args, **kwargs)
        on_call(arguments=arguments)
        started: float = time.perf_counter()
        try:
            result: R = function(*args, **kwargs)
        except Exception as error:
            on_error(arguments=arguments, error=error, duration_ms=elapsed_ms(started=started))
            raise
        on_return(arguments=arguments, result=result, duration_ms=elapsed_ms(started=started))
        return result

    return wrapper


def elapsed_ms(*, started: float) -> float:
    return round((time.perf_counter() - started) * MILLISECONDS_PER_SECOND, 1)
