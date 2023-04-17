# =================================================================
#
# Authors: Tom Kralidis <tomkralidis@gmail.com>
#
# Copyright (c) 2022 Tom Kralidis
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

import logging
from pathlib import Path
from typing import Dict, Tuple

from pygeoapi.models.processes import (
    Execution,
    JobStatus,
    Link,
    ProcessDescription,
    ProcessInput,
    ProcessIOSchema,
    ProcessIOType,
    ProcessJobControlOption,
    ProcessOutput,
    ProcessOutputTransmissionMode,
)
from pygeoapi.process.base import BaseProcessor, ProcessorExecuteError


LOGGER = logging.getLogger(__name__)


class HelloWorldProcessor(BaseProcessor):
    """Hello World Processor example"""

    process_metadata = ProcessDescription(
        title={
            'en': 'Hello World',
            'fr': 'Bonjour le Monde'
        },
        description={
            'en': 'An example process that takes a name as input, and echoes '
                  'it back as output. Intended to demonstrate a simple '
                  'process with a single literal input.',
            'fr': 'Un exemple de processus qui prend un nom en entrée et le '
                  'renvoie en sortie. Destiné à démontrer un processus '
                  'simple avec une seule entrée littérale.',
        },
        keywords=[
            'hello world',
            'example',
            'echo'
        ],
        version="0.2.0",
        id="hello-world",
        jobControlOptions=[
            ProcessJobControlOption.SYNC_EXECUTE,
            ProcessJobControlOption.ASYNC_EXECUTE,
        ],
        outputTransmission=[ProcessOutputTransmissionMode.VALUE],
        links=[
            Link(
                type="text/html",
                rel="about",
                title="information",
                href="https://example.org/process",
                hreflang="en-US"
            )
        ],
        inputs={
            "name": ProcessInput(
                title="Name",
                description=(
                    'The name of the person or entity that you wish to be echoed '
                    'back as an output'
                ),
                schema=ProcessIOSchema(
                    type=ProcessIOType.STRING),
                keywords=[
                    "full name",
                    "personal"
                ]
            ),
            "message": ProcessInput(
                title="Message",
                description='An optional message to echo as well',
                schema=ProcessIOSchema(
                    type=ProcessIOType.STRING),
                minOccurs=0,
                keywords=[
                    "message"
                ]
            )
        },
        outputs={
            "echo": ProcessOutput(
                title="Hello world",
                description=(
                    'A "hello world" echo with the name and (optional) message '
                    'submitted for processing'
                ),
                schema=ProcessIOSchema(
                    type=ProcessIOType.OBJECT,
                    contentMediaType="application/json"
                )
            )
        },
        example={
            "inputs": {"name": "World", "message": "An optional message."}
        }
    )

    def execute(
            self,
            job_id: str,
            execution_request: Execution
    ) -> Tuple[JobStatus, Dict[str, str]]:
        inputs = execution_request.dict().get("inputs", {})
        name = inputs.get("name")
        if name is None:
            raise ProcessorExecuteError('Cannot process without a name')
        message = inputs.get('message', '')
        echo_value = f'Hello {name}! {message}'.strip()
        echo_location = (
                Path.home() / self.metadata["id"] / f"{job_id}-echo.txt")
        with echo_location.open(mode="w", encoding="utf-8") as fh:
            fh.write(echo_value)
        result = {
            "echo": str(echo_location)
        }
        return JobStatus.successful, result

    def __repr__(self):
        return f'<HelloWorldProcessor> {self.process_metadata.id}'
