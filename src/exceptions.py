"""Errors presented concisely by the CLI; causes remain in the log."""


class PipelineError(Exception):
    pass


class ConfigError(PipelineError):
    pass


class COMSOLConnectionError(PipelineError):
    pass


class COMSOLModelError(PipelineError):
    pass


class COMSOLResultNotFoundError(PipelineError):
    pass


class CSVFormatError(PipelineError):
    pass


class DataProcessingError(PipelineError):
    pass


class OriginConnectionError(PipelineError):
    pass


class OriginPlotError(PipelineError):
    pass


class OriginExportError(PipelineError):
    pass
