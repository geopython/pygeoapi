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
from typing import Dict, Tuple

from pygeoapi.models.processes import (
    Execution,
    JobStatus,
    ProcessDescription,
)

LOGGER = logging.getLogger(__name__)


class BaseProcessor:
    """generic Processor ABC. Processes are inherited from this class"""
    process_metadata: ProcessDescription

    def execute(
            self,
            job_id: str,
            execution_request: Execution
    ) -> Tuple[JobStatus, Dict[str, str]]:
        """
        execute the process

        :returns: tuple of job status and a dict with output ids as keys and
                  location for persisted results as values
        """

        raise NotImplementedError()

    def __repr__(self):
        return f'<BaseProcessor> {self.process_metadata.id}'


class ProcessorGenericError(Exception):
    """processor generic error"""
    pass


class ProcessorExecuteError(ProcessorGenericError):
    """query / backend error"""
    pass
