import os
from pathlib import Path
from typing import Dict, List, Tuple

import pygeoapi


def get_stream_branch(self: "SpeckleProvider", client: "SpeckleClient", wrapper: "StreamWrapper") -> Tuple:
    """Get stream and branch from the server."""
    
    from specklepy.logging.exceptions import SpeckleException

    branch = None
    stream = client.stream.get(
        id = wrapper.stream_id, branch_limit=100
    )

    if isinstance(stream, Exception):
        raise SpeckleException(stream.message+ ", "+ self.speckle_url)

    for br in stream['branches']['items']:
        if br['id'] == wrapper.model_id:
            branch = br
            break
    return stream, branch
    
def get_client(wrapper: "StreamWrapper", url_proj: str) -> "SpeckleClient":
    """Get unauthenticated SpeckleClient."""

    from specklepy.core.api.client import SpeckleClient

    # get client by URL, no authentication
    client = SpeckleClient(host=wrapper.host, use_ssl=wrapper.host.startswith("https"))
    client.account.serverInfo.url = url_proj.split("/projects")[0]
    return client


def get_comments(client: "SpeckleClient", project_id: str, model_id: str):
    """Query comments from the Project and Model (if recorded in Comment)."""

    from gql import gql
    from specklepy.logging.exceptions import SpeckleException, SpeckleInvalidUnitException

    # get Project data
    query = gql(
        """
        query Comments ($project_id: String!) {
        project(id: $project_id) {
            commentThreads {
            totalCount
            items{
                
                id
                author{
                name
                }
                createdAt
                rawText
                
                text{
                attachments{
                    id
                    fileName
                    fileType
                    fileSize
                }
                }
                viewerResources{
                modelId
                }
                viewerState
                
                replies{
                items{
                    
                    id
                    author{
                    name
                    }
                    createdAt
                    rawText
                    
                    text{
                    attachments{
                        id
                        fileName
                        fileType
                        fileSize
                    }
                    }
                    viewerResources{
                    modelId
                    }
                    viewerState
                    
                }
                }
                
            }
            }
        }
        }
    """
    )
    params = {
        "project_id": project_id,
    }
    response_data = client.httpclient.execute(query, params)
    threads = response_data["project"]["commentThreads"]["items"]
    threads_objs = {}
    for thread in threads:
        comment_data = get_info_from_comment(thread, project_id, model_id)
        if comment_data is None:
            continue

        # unpack object
        comm_id, position, author_name, created_date, raw_text, attachments_paths, res_id = comment_data
        threads_objs[comm_id] = {
            "position": position, 
            "items": [{
                "author": author_name,
                "date": created_date,
                "text": raw_text,
                "attachments": attachments_paths,
                "resource_id": res_id,
                }]
            }
        replies = thread["replies"]["items"]
        for reply in replies:
            reply_data = get_info_from_comment(reply, project_id, model_id)
            if reply_data is None:
                continue

            # unpack reply 
            _, position, author_name_reply, created_date_reply, raw_text_reply, attachments_paths_reply, _ = reply_data
        
            threads_objs[comm_id]["items"].append(
                {
                "author": author_name_reply,
                "date": created_date_reply,
                "text": raw_text_reply,
                "attachments": attachments_paths_reply,
                }
            )
    
    return threads_objs


def get_info_from_comment(comment: Dict, project_id: str, model_id: str) -> Tuple [str, List[float], str, str, str, List[str]]:
    """Get displayable data from commit."""

    comm_id = comment["id"]
    author_name = comment["author"]["name"]
    created_date = comment["createdAt"]
    raw_text = comment["rawText"]

    r'''
    resources = comment["viewerResources"]
    model_found = 1
    # assume the model is matching, only exclude if other model_id is stated
    for resource in resources:
        if resource["modelId"] == model_id:
            break
        if resource["modelId"] is not None and resource["modelId"]!="" and resource["modelId"] != model_id:
            # wrong model, don't include
            model_found = 0
    '''
    position = [0,0,0]
    res_id = model_id
    viewer_state = comment["viewerState"]
    if viewer_state is not None: # can be None for Replies
        position: List[float] = viewer_state["ui"]["camera"]["target"]
        try:
            res_id = viewer_state["resources"]["request"]["resourceIdString"]
        except:
            pass

    attachments = comment["text"]["attachments"]
    attachments_paths = []
    for attach in attachments:
        try:
            file_path = get_attachment(project_id, attach["id"], attach["fileName"])
            attachments_paths.append(file_path)
        except:
            pass # attachment was not queried successfully

    #if model_found is False:
    #    return None
    return comm_id, position, author_name, created_date, raw_text, attachments_paths, res_id

def get_attachment(project_id: str, attachment_id: str, attachment_name: str) -> Path:

    import requests
    import shutil

    return attachment_name

    file_path_obj: Path = Path(Path(pygeoapi.__file__).parent.parent, "Temp_attachments", attachment_name)
    print(file_path_obj)
    file_path = str(file_path_obj)
    print(file_path)

    if os.path.isfile(file_path) is True: # if already saved
        return file_path
    
    url = f"https://speckle.xyz/api/stream/{project_id}/blob/{attachment_id}"
    headers = {"User-Agent": "Speckle Pygeoapi"}
    r = requests.get(url, headers=headers, stream=True)
    
    if r.status_code == 200:
        with open(file_path, "wb") as f:
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)
        return file_path
    else:
        raise Exception(
            f"Request not successful: Response code {r.status_code}"
        )
    