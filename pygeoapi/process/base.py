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
from typing import Callable, Dict, Optional

from pygeoapi.models.processes import (
    ExecuteRequest,
    JobStatusInfoInternal,
    ProcessDescription,
)

LOGGER = logging.getLogger(__name__)


class BaseProcessor:
    """generic Processor ABC. Processes are inherited from this class"""
    process_metadata: ProcessDescription

    def __init__(self, processor_def: Dict):
        """Initialize processor.

        The ``processor_def`` parameter may be used to pass initialization
        options for the processor (however, the default implementation does
        not use it).

        :param processor_def: processor definition
        """
        ...

    def execute(
            self,
            job_id: str,
            execution_request: ExecuteRequest,
            results_storage_root: Path,
            progress_reporter: Optional[
                Callable[[JobStatusInfoInternal], bool]
            ] = None
    ) -> JobStatusInfoInternal:
        """Execute the process

        Processes are expected to handle persistence of their own results.
        Long-running processes may report execution progress by calling the
        input ``progress_reporter`` with an instance of
        ``JobStatusInfoInternal``. Note that it is not necessary for a project
        to initialize nor finalize its status, as the process manager already
        performs those tasks.


        :param job_id: identifier of the job
        :param execution_request: execution parameters
        :param results_storage_root: where to store processing outputs
        :param progress_reporter: A callable that can be used to report
                                  execution progress

        :raise: JobFailedError: If there is an error during execution
        :returns: status info with relevant detail about the finished execution
        """

        raise NotImplementedError()

    def __repr__(self):
        return f'<BaseProcessor> {self.process_metadata.id}'
