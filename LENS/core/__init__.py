from python_toolbox.project.config import Base_Config
from python_toolbox.registry import Registry

config_registry = Registry[type[Base_Config]]("config", Base_Config)
