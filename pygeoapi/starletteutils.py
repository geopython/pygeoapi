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
    ImmutableMultiDict,
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


class PygeoapiQueryParams(QueryParams):
    """Reimplemented in order to convert query parameter names to lowercase.

    This is useful when used to parse URL query parameters, which can usually
    be specified with whatever casing.

    Implementation is based on starlette's ``QueryParams`` class and it simply
    converts any incoming keys to lower case.

    """

    def __init__(
            self,
            *args: typing.Union[
                ImmutableMultiDict,
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
    """
    Custom starlette request class that allows using custom query param parser.

    The default starlette ``Request`` is hardcoded to use starlette's
    ``QueryParams`` class for parsing a request's query parameters. We want
    to use a custom parser instead (``PygeoapiQueryParams``).

    """

    query_params_class = PygeoapiQueryParams

    @property
    def query_params(self) -> QueryParams:
        if not hasattr(self, "_query_params"):
            self._query_params = self.query_params_class(
                self.scope["query_string"])
        return self._query_params


def pygeoapi_request_response(
        func: typing.Callable,
        request_class: typing.Optional[typing.Type] = Request
) -> ASGIApp:
    """
    This is a reimplementation of ``starlette.routing.request_response`` that
    takes an optional parameter with a custom request class to use instead of
    starlette's ``Request``.
    """

    is_coroutine = iscoroutinefunction_or_partial(func)

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        request = request_class(scope, receive=receive, send=send)
        if is_coroutine:
            response = await func(request)
        else:
            response = await run_in_threadpool(func, request)
        await response(scope, receive, send)

    return app


class PygeoapiRoute(Route):
    """Reimplemented in order to be able to use a custom request class.

    The default starlette ``Route`` delegates creation of starlette ``Request``
    instances to the ``starlette.routing.request_response`` function. In order
    to be able to use a custom request class we need to use a custom function
    instead. This class is pretty much the same as its base class, with the
    only change being that it calls ``pygeoapi_request_response`` instead of
    ``starlette.routing.request_response``.

    """

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
            # Endpoint is function or method.
            # Treat it as `func(request) -> response`.
            self.app = pygeoapi_request_response(
                endpoint, request_class=PygeoapiStarletteRequest)
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
    route_class = PygeoapiRoute

    def add_route(
            self,
            path: str,
            endpoint: typing.Callable,
            methods: typing.List[str] = None,
            name: str = None,
            include_in_schema: bool = True,
    ) -> None:
        route = self.route_class(
            path,
            endpoint=endpoint,
            methods=methods,
            name=name,
            include_in_schema=include_in_schema,
        )
        self.routes.append(route)


class PygeoapiStarlette(Starlette):
    """Custom starlette application that allows using a different router class.

    The default starlette ``Starlette`` application is hardcoded to use
    starlette's ``Router`` class for handling routing in the application. We
    want to be able to specify some custom behavior for starlette's requests
    and the request is handled by starlette's routes, which in tunr are handled
    by starlette's router.

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
            router_class: typing.Optional[typing.Type] = Router,
    ) -> None:
        # The lifespan context function is a newer style that replaces
        # on_startup / on_shutdown handlers. Use one or the other, not both.
        assert lifespan is None or (
                on_startup is None and on_shutdown is None
        ), "Use either 'lifespan' or 'on_startup'/'on_shutdown', not both."

        self._debug = debug
        self.state = State()
        self.router = router_class(
            routes,
            on_startup=on_startup,
            on_shutdown=on_shutdown,
            lifespan=lifespan
        )
        self.exception_handlers = (
            {} if exception_handlers is None else dict(exception_handlers)
        )
        self.user_middleware = [] if middleware is None else list(middleware)
        self.middleware_stack = self.build_middleware_stack()