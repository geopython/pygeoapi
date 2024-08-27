import json
from typing import Dict, List, Optional
from warnings import warn

import requests

from specklepy.core.api.client import SpeckleClient
from specklepy.core.api.credentials import Account, get_account_from_token
from specklepy.logging.exceptions import SpeckleException, SpeckleWarning
from specklepy.transports.abstract_transport import AbstractTransport

from .batch_sender import BatchSender


class ServerTransport(AbstractTransport):
    """
    The `ServerTransport` is the vehicle through which you transport objects to and
    from a Speckle Server. Provide it to `operations.send()` or `operations.receive()`.

    The `ServerTransport` can be authenticated two different ways:
        1. by providing a `SpeckleClient`
        2. by providing an `Account`
        3. by providing a `token` and `url`

    ```py
    from specklepy.api import operations
    from specklepy.transports.server import ServerTransport

    # here's the data you want to send
    block = Block(length=2, height=4)

    # next create the server transport - this is the vehicle through which
    # you will send and receive
    transport = ServerTransport(stream_id=new_stream_id, client=client)

    # this serialises the block and sends it to the transport
    hash = operations.send(base=block, transports=[transport])

    # you can now create a commit on your stream with this object
    commit_id = client.commit.create(
        stream_id=new_stream_id,
        obj_id=hash,
        message="this is a block I made in speckle-py",
    )
    ```
    """

    def __init__(
        self,
        stream_id: str,
        client: Optional[SpeckleClient] = None,
        account: Optional[Account] = None,
        token: Optional[str] = None,
        url: Optional[str] = None,
        name: str = "RemoteTransport",
    ) -> None:
        super().__init__()
        if client is None and account is None and token is None and url is None:
            raise SpeckleException(
                "You must provide either a client or a token and url to construct a"
                " ServerTransport."
            )

        self._name = name
        self.account = None
        self.saved_obj_count = 0
        if account:
            self.account = account
            url = account.serverInfo.url
        elif client:
            url = client.url
            if not client.account.token:
                warn(
                    SpeckleWarning(
                        "Unauthenticated Speckle Client provided to Server Transport"
                        f" for {url}. Receiving from private streams will fail."
                    )
                )
            else:
                self.account = client.account
        else:
            self.account = get_account_from_token(token, url)

        self.stream_id = stream_id
        self.url = url

        self.session = requests.Session()

        if self.account.token is not None:
            self._batch_sender = BatchSender(
                self.url, self.stream_id, self.account.token, max_batch_size_mb=1
            )
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.account.token}",
                    "Accept": "text/plain",
                }
            )

    @property
    def name(self) -> str:
        return self._name

    def begin_write(self) -> None:
        self.saved_obj_count = 0

    def end_write(self) -> None:
        self._batch_sender.flush()

    def save_object(self, id: str, serialized_object: str) -> None:
        self._batch_sender.send_object(id, serialized_object)

    def save_object_from_transport(
        self, id: str, source_transport: AbstractTransport
    ) -> None:
        obj_string = source_transport.get_object(id=id)
        self.save_object(id=id, serialized_object=obj_string)

    def get_object(self, id: str) -> str:
        # endpoint = f"{self.url}/objects/{self.stream_id}/{id}/single"
        # r = self.session.get(endpoint, stream=True)

        # _, obj = next(r.iter_lines().decode("utf-8")).split("\t")

        # return obj

        raise SpeckleException(
            "Getting a single object using `ServerTransport.get_object()` is not"
            " implemented. To get an object from the server, please use the"
            " `SpeckleClient.object.get()` route",
            NotImplementedError(),
        )

    def has_objects(self, id_list: List[str]) -> Dict[str, bool]:
        return {id: False for id in id_list}

    def copy_object_and_children(
        self, id: str, target_transport: AbstractTransport
    ) -> str:
        endpoint = f"{self.url}/objects/{self.stream_id}/{id}/single"
        r = self.session.get(endpoint)
        r.encoding = "utf-8"

        if r.status_code != 200:
            raise SpeckleException(
                f"Can't get object {self.stream_id}/{id}: HTTP error"
                f" {r.status_code} ({r.text[:1000]})"
            )
        root_obj_serialized = r.text
        root_obj = json.loads(root_obj_serialized)
        closures = root_obj.get("__closure", {})

        # Check which children are not already in the target transport
        children_ids = list(closures.keys())
        children_found_map = target_transport.has_objects(children_ids)
        new_children_ids = [
            id for id in children_found_map if not children_found_map[id]
        ]

        # Get the new children
        endpoint = f"{self.url}/api/getobjects/{self.stream_id}"
        r = self.session.post(
            endpoint, data={"objects": json.dumps(new_children_ids)}, stream=True
        )
        r.encoding = "utf-8"
        lines = r.iter_lines(decode_unicode=True, delimiter="},{")

        # iter through returned objects saving them as we go
        target_transport.begin_write()
        all_lines = [line for _,line in enumerate(lines)]
        for i, line in enumerate(all_lines):
            if line:
                hash = line.split('"id": "')[1].split('"')[0]
                obj = "{" + line + "}"
                if i==0:
                    obj = obj[2:]
                elif i==len(all_lines)-1:
                    obj = obj[:-2]
                target_transport.save_object(hash, obj)

        target_transport.save_object(id, root_obj_serialized)
        target_transport.end_write()

        return root_obj_serialized
