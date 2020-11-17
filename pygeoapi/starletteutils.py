# =================================================================
#
# Authors: Ricardo Garcia Silva <ricardo.garcia.silva@gmail.com>
#
# Copyright (c) 2020 Ricardo Garcia Silva
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# =================================================================

"""Custom starlette utilities"""

import functools
import inspect
import typing

from starlette.applications import Starlette
from starlette.datastructures import (
    QueryParams,
    State,
)
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.routing import (
    BaseRoute,
    compile_path,
    iscoroutinefunction_or_partial,
    get_name,
    Route,
    Router,
    request_response,
    run_in_threadpool,
)
from starlette.types import (
    ASGIApp,
    Receive,
    Scope,
    Send,
)

# customize starlette application in order to supply a custom router
# customize starlette router in order to supply a custom request_response function...


class PygeoapiQueryParams(QueryParams):
    """
    Reimplemented in order to convert all query parameter names to lowercase
    """

    def __init__(
            self,
            *args: typing.Union[
                "ImmutableMultiDict",
                typing.Mapping,
                typing.List[typing.Tuple[typing.Any, typing.Any]],
                str,
                bytes,
            ],
            **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._list = [(k.lower(), v) for k, v in self._list]
        self._dict = {k.lower(): str(v) for k, v in self._dict.items()}



class PygeoapiStarletteRequest(Request):

    @property
    def query_params(self) -> QueryParams:
        if not hasattr(self, "_query_params"):
            self._query_params = PygeoapiQueryParams(self.scope["query_string"])
        return self._query_params


def pygeoapi_request_response(func: typing.Callable) -> ASGIApp:
    """
    Takes a function or coroutine `func(request) -> response`,
    and returns an ASGI application.

    Reimplemented in order to be able to specify a custom starlette Request
    class

    """

    is_coroutine = iscoroutinefunction_or_partial(func)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = PygeoapiStarletteRequest(scope, receive=receive, send=send)
        if is_coroutine:
            response = await func(request)
        else:
            response = await run_in_threadpool(func, request)
        await response(scope, receive, send)

    return app


class PygeoapiRoute(Route):
    """Reimplemented in order to supply a custom Request class"""

    def __init__(
            self,
            path: str,
            endpoint: typing.Callable,
            *,
            methods: typing.List[str] = None,
            name: str = None,
            include_in_schema: bool = True,
    ) -> None:
        assert path.startswith("/"), "Routed paths must start with '/'"
        self.path = path
        self.endpoint = endpoint
        self.name = get_name(endpoint) if name is None else name
        self.include_in_schema = include_in_schema

        endpoint_handler = endpoint
        while isinstance(endpoint_handler, functools.partial):
            endpoint_handler = endpoint_handler.func
        if inspect.isfunction(endpoint_handler) or inspect.ismethod(endpoint_handler):
            # Endpoint is function or method. Treat it as `func(request) -> response`.
            self.app = pygeoapi_request_response(endpoint)
            if methods is None:
                methods = ["GET"]
        else:
            # Endpoint is a class. Treat it as ASGI.
            self.app = endpoint

        if methods is None:
            self.methods = None
        else:
            self.methods = {method.upper() for method in methods}
            if "GET" in self.methods:
                self.methods.add("HEAD")

        self.path_regex, self.path_format, self.param_convertors = compile_path(path)


class PygeoapiRouter(Router):
    """Reimplemented in order to supply a custom Route class"""

    def add_route(
            self,
            path: str,
            endpoint: typing.Callable,
            methods: typing.List[str] = None,
            name: str = None,
            include_in_schema: bool = True,
    ) -> None:
        route = PygeoapiRoute(
            path,
            endpoint=endpoint,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
        )
        self.routes.append(route)


class PygeoapiStarlette(Starlette):
    """Reimplemented in order to supply a custom Router class

    Pygeoapi is subclassing the default Starlette class in order to be able to
    control starlette's Request class. This goal is accomplishd by
    reimplementing a starlette application's default router.

    """

    def __init__(
            self,
            debug: bool = False,
            routes: typing.Sequence[BaseRoute] = None,
            middleware: typing.Sequence[Middleware] = None,
            exception_handlers: typing.Dict[
                typing.Union[int, typing.Type[Exception]], typing.Callable
            ] = None,
            on_startup: typing.Sequence[typing.Callable] = None,
            on_shutdown: typing.Sequence[typing.Callable] = None,
            lifespan: typing.Callable[["Starlette"], typing.AsyncGenerator] = None,
    ) -> None:
        # The lifespan context function is a newer style that replaces
        # on_startup / on_shutdown handlers. Use one or the other, not both.
        assert lifespan is None or (
                on_startup is None and on_shutdown is None
        ), "Use either 'lifespan' or 'on_startup'/'on_shutdown', not both."

        self._debug = debug
        self.state = State()
        self.router = PygeoapiRouter(
            routes, on_startup=on_startup, on_shutdown=on_shutdown, lifespan=lifespan
        )
        self.exception_handlers = (
            {} if exception_handlers is None else dict(exception_handlers)
        )
        self.user_middleware = [] if middleware is None else list(middleware)
        self.middleware_stack = self.build_middleware_stack()