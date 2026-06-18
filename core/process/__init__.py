from python_toolbox.registry import Registry
from ._base import Base_Process

pipeline_registry = Registry[type[Base_Process]]("pipeline", Base_Process)
