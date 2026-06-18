from python_toolbox.registry import Registry

from ._base import Base_Reader

reader_registry = Registry[type[Base_Reader]]("Reader", Base_Reader)
