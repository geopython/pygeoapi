class JobError(Exception):
    ...


class InvalidJobParametersError(JobError):
    ...


class JobNotFoundError(JobError):
    ...


class JobNotReadyError(JobError):
    ...


class JobFailedError(JobError):
    ...


class ProcessError(Exception):
    ...


class UnknownProcessError(ProcessError):
    ...
