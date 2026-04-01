import structlog
import uuid
import contextvars
from structlog.processors import JSONRenderer, TimeStamper

trace_id_var = contextvars.ContextVar('trace_id', default='')

def add_trace_id(logger, method_name, event_dict):
    trace_id = trace_id_var.get()
    if trace_id:
        event_dict['trace_id'] = trace_id
    return event_dict

def setup_logger(agent_name: str = "irisquant"):
    structlog.configure(
        processors=[TimeStamper(fmt="iso"), add_trace_id, structlog.stdlib.add_logger_name, structlog.stdlib.add_log_level, JSONRenderer()],
        context_class=dict, logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger, cache_logger_on_first_use=True,
    )
    logger = structlog.get_logger(agent_name).bind(agent=agent_name)
    logger._agent_name = agent_name
    return logger

def get_trace_id() -> str:
    trace_id = trace_id_var.get()
    if not trace_id:
        trace_id = str(uuid.uuid4())
        trace_id_var.set(trace_id)
    return trace_id

def new_trace_context() -> str:
    trace_id = str(uuid.uuid4())
    trace_id_var.set(trace_id)
    return trace_id
